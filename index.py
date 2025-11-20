import streamlit as st
import psycopg2
from psycopg2 import sql
from psycopg2 import extras
from datetime import date
import uuid
import pandas as pd
import io

# --- Configuration and Initial State ---
st.set_page_config(
    page_title="Employee Admin Dashboard",
    page_icon="🏢",
    layout="centered",
    initial_sidebar_state="expanded"
)

TABLE_NAME = "employees"

# Initialize Session State
if 'db_conn' not in st.session_state:
    st.session_state.db_conn = None
if 'use_mock_db' not in st.session_state:
    st.session_state.use_mock_db = True
if 'mock_employees' not in st.session_state:
    st.session_state.mock_employees = [
        {"id": str(uuid.uuid4()), "name": "Alice Johnson (Mock)", "email": "alice@mock.com", "birthday": date(1990, 1, 1), "last_wished_year": 1900},
        {"id": str(uuid.uuid4()), "name": "Bob Lee (Mock)", "email": "bob@mock.com", "birthday": date(1985, 12, 25), "last_wished_year": 1900}
    ]

# --- Database Management Functions ---

@st.cache_resource(ttl=3600)
def establish_db_connection(db_url):
    """Attempts to establish and cache the PostgreSQL connection."""
    try:
        # Clean the URL if the user accidentally pastes the problematic parameter
        cleaned_url = db_url.replace("&channel_binding=require", "")
        conn = psycopg2.connect(cleaned_url)
        conn.autocommit = False 
        return conn
    except Exception:
        return None

def init_real_db(connection):
    """Ensures the employees table exists with the required schema."""
    cursor = connection.cursor()
    try:
        upsert_query = sql.SQL("""
                INSERT INTO {} (name, email, birthday) 
                VALUES (%s, %s, %s)  # <--- CRUCIAL: Must have three %s placeholders
                ON CONFLICT (email) DO UPDATE 
                SET name = EXCLUDED.name, 
                    birthday = EXCLUDED.birthday;
            """).format(sql.Identifier(TABLE_NAME))
            
            # Use execute_batch for performance
            extras.execute_batch(cursor, upsert_query, data_to_upload)
            conn.commit()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")
        connection.rollback()
    finally:
        cursor.close()

# --- NEW: Check for Secrets on Startup ---

# Check if secrets are available and attempt connection automatically
if st.session_state.use_mock_db and 'database' in st.secrets and 'url' in st.secrets.database:
    secret_url = st.secrets.database.url
    conn_attempt = establish_db_connection(secret_url)
    
    if conn_attempt:
        init_real_db(conn_attempt)
        st.session_state.db_conn = conn_attempt
        st.session_state.use_mock_db = False
        # Do not st.rerun here, let the script finish initializing
    else:
        st.sidebar.error("Attempted connection via secrets.toml but failed. Check URL.")


# --- Connection UI in Sidebar ---

def connection_ui():
    """Renders the connection input and handles state transition."""
    st.sidebar.title("🔗 DB Connection Setup")
    
    # Status Indicator
    if st.session_state.use_mock_db:
        st.sidebar.warning("Status: **MOCK MODE** (Data is temporary)")
    else:
        st.sidebar.success("Status: **REAL DB MODE** (Neon DB Connected)")

    # Expander for connection details, expanded by default in mock mode
    with st.sidebar.expander("Configure Manual DB URL", expanded=st.session_state.use_mock_db):
        db_url_input = st.text_input(
            "Enter Full Neon DB Connection URL",
            placeholder="postgresql://user:password@host:port/dbname?sslmode=require",
            type="password", 
            key="db_url_live_input"
        )
        
        if st.button("Connect & Initialize DB", key="connect_button"):
            if not db_url_input:
                st.sidebar.warning("Please paste your connection URL.")
                return

            with st.spinner("Attempting connection..."):
                # Pass the input URL to the connection attempt
                conn_attempt = establish_db_connection(db_url_input.strip())
            
            if conn_attempt:
                init_real_db(conn_attempt)
                st.session_state.db_conn = conn_attempt
                st.session_state.use_mock_db = False
                st.toast("Connection successful! Switching to Real DB mode.")
                st.rerun() 
            else:
                st.sidebar.error("Manual connection failed. Check your URL.")


# --- Unified CRUD Logic ---

conn = st.session_state.db_conn
USE_MOCK_DB = st.session_state.use_mock_db

def add_employee(name, email, birthday):
    """Adds an employee to the mock list or the real DB."""
    if USE_MOCK_DB:
        # Mock DB Logic
        if any(emp['email'] == email for emp in st.session_state.mock_employees):
            st.error(f"Error: An employee with email '{email}' already exists in the mock DB.")
            return False
        new_emp = {"id": str(uuid.uuid4()), "name": name, "email": email, "birthday": birthday, "last_wished_year": 1900}
        st.session_state.mock_employees.append(new_emp)
        return True
    else:
        # Real DB Logic
        cursor = conn.cursor()
        try:
            # Upsert logic (Insert OR Update if email exists)
            upsert_query = sql.SQL("""
                INSERT INTO {} (name, email, birthday) 
                VALUES (%s, %s, %s)
                ON CONFLICT (email) DO UPDATE 
                SET name = EXCLUDED.name, 
                    birthday = EXCLUDED.birthday;
            """).format(sql.Identifier(TABLE_NAME))
            cursor.execute(upsert_query, (name, email, birthday))
            conn.commit()
            return True
        except Exception as e:
            st.error(f"Error adding/updating employee: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

def bulk_upload_csv(df):
    """Inserts or updates multiple employees from a DataFrame."""
    if df.empty:
        st.warning("CSV file is empty.")
        return 0, 0, 0

    required_cols = ['name', 'email', 'birthday']
    if not all(col in df.columns for col in required_cols):
        st.error(f"CSV must contain columns: {', '.join(required_cols)}")
        return 0, 0, 0

    df = df[required_cols].dropna(subset=['email'])
    
    # Try to convert birthday column to date objects
    try:
        df['birthday'] = pd.to_datetime(df['birthday'], errors='coerce').dt.date
        df.dropna(subset=['birthday'], inplace=True)
    except Exception:
        st.error("Could not parse all dates in the 'birthday' column.")
        return 0, 0, 0

    data_to_upload = [(row['name'], row['email'], row['birthday']) for index, row in df.iterrows()]
    
    if USE_MOCK_DB:
        # Mock DB Bulk Upsert Logic
        inserted_count = 0
        updated_count = 0
        
        for name, email, birthday in data_to_upload:
            is_found = False
            for emp in st.session_state.mock_employees:
                if emp['email'] == email:
                    emp['name'] = name
                    emp['birthday'] = birthday
                    updated_count += 1
                    is_found = True
                    break
            if not is_found:
                new_emp = {"id": str(uuid.uuid4()), "name": name, "email": email, "birthday": birthday, "last_wished_year": 1900}
                st.session_state.mock_employees.append(new_emp)
                inserted_count += 1
        
        st.success(f"Mock Data Updated: {inserted_count} inserted, {updated_count} updated.")
        return inserted_count, updated_count, len(df) - inserted_count - updated_count
    
    else:
        # Real DB Bulk Upsert Logic
        cursor = conn.cursor()
        
        try:
            # Query with ON CONFLICT for upsert
            upsert_query = sql.SQL("""
                INSERT INTO {} (name, email, birthday) 
                VALUES %s
                ON CONFLICT (email) DO UPDATE 
                SET name = EXCLUDED.name, 
                    birthday = EXCLUDED.birthday;
            """).format(sql.Identifier(TABLE_NAME))
            
            # Use execute_batch for performance
            extras.execute_batch(cursor, upsert_query, data_to_upload)
            conn.commit()
            
            # Simple count (does not distinguish insert/update count easily with execute_batch)
            st.success(f"Bulk Upload Complete: Successfully processed {len(data_to_upload)} records (Inserted or Updated).")
            return len(data_to_upload), 0, 0 

        except Exception as e:
            st.error(f"Bulk upload failed during DB execution: {e}")
            conn.rollback()
            return 0, 0, len(data_to_upload)
        finally:
            cursor.close()

def get_employee_names():
    # Implementation remains the same
    if USE_MOCK_DB:
        return sorted([emp['name'] for emp in st.session_state.mock_employees])
    else:
        if not conn: return []
        cursor = conn.cursor()
        try:
            cursor.execute(sql.SQL("SELECT name FROM {} ORDER BY name").format(sql.Identifier(TABLE_NAME)))
            return [row[0] for row in cursor.fetchall()]
        except Exception as e:
            st.error(f"Error fetching names: {e}")
            return []
        finally:
            cursor.close()

def get_employee_details(name):
    # Implementation remains the same
    if USE_MOCK_DB:
        return next((emp for emp in st.session_state.mock_employees if emp['name'] == name), None)
    else:
        if not conn: return None
        cursor = conn.cursor()
        try:
            select_query = sql.SQL("SELECT name, email, birthday, last_wished_year FROM {} WHERE name = %s").format(sql.Identifier(TABLE_NAME))
            cursor.execute(select_query, (name,))
            result = cursor.fetchone()
            if result:
                # Ensure the date is returned as a date object if possible
                return {"name": result[0], "email": result[1], "birthday": result[2], "last_wished_year": result[3]}
            return None
        except Exception as e:
            st.error(f"Error fetching details: {e}")
            return None
        finally:
            cursor.close()

def delete_employee(name):
    # Implementation remains the same
    if USE_MOCK_DB:
        initial_count = len(st.session_state.mock_employees)
        st.session_state.mock_employees = [emp for emp in st.session_state.mock_employees if emp['name'] != name]
        return len(st.session_state.mock_employees) < initial_count
    else:
        if not conn: return False
        cursor = conn.cursor()
        try:
            delete_query = sql.SQL("DELETE FROM {} WHERE name = %s").format(sql.Identifier(TABLE_NAME))
            cursor.execute(delete_query, (name,))
            rows_deleted = cursor.rowcount
            conn.commit()
            return rows_deleted > 0
        except Exception as e:
            st.error(f"Error deleting employee: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

# --- Main Application UI ---
connection_ui() # Render connection panel in the sidebar

st.title("🎂 Employee Management Panel")
st.markdown("A simple admin interface for managing employee birthdays.")
st.markdown("---")

# --- Tabs for CRUD Operations ---

tab_add, tab_find, tab_delete = st.tabs(["➕ Add/Import Employee", "🔍 Find Employee & Details", "🗑️ Delete Employee"])

# 1. Add Employee Tab
with tab_add:
    st.header("New Employee Entry or Bulk Import")
    
    add_tab, import_tab = st.tabs(["👤 Add Single Employee", "📁 Bulk Upload (CSV)"])

    with add_tab:
        with st.form("add_employee_form", clear_on_submit=True):
            col_name, col_email = st.columns(2)
            with col_name:
                new_name = st.text_input("Full Name", max_chars=255, help="e.g., Emily Clark")
            with col_email:
                new_email = st.text_input("Email Address", max_chars=255, help="Must be unique.")
            
            new_birthday = st.date_input(
                "Birthday (Date Picker)",
                min_value=date(1900, 1, 1),
                max_value=date.today(),
                value=date(2000, 1, 1),
                help="Select the date of birth (YYYY-MM-DD)."
            )

            submitted = st.form_submit_button("✅ Add Employee (Single)", type="primary")

            if submitted:
                if new_name and new_email:
                    with st.spinner(f"Adding/Upserting {new_name}..."):
                        if add_employee(new_name.strip(), new_email.strip(), new_birthday):
                            st.success(f"Successfully added/updated {new_name}!")
                            st.balloons()
                else:
                    st.warning("Please fill in the Name and Email fields.")

    with import_tab:
        st.markdown("Upload a CSV file with the following required columns:")
        st.code("name, email, birthday")
        
        uploaded_file = st.file_uploader("Choose a CSV file", type="csv")
        
        if uploaded_file is not None:
            # Read CSV into a pandas DataFrame
            try:
                data = io.StringIO(uploaded_file.getvalue().decode("utf-8"))
                df = pd.read_csv(data)
                
                st.info(f"Loaded {len(df)} rows from CSV. Processing for upload...")
                
                if st.button("🚀 Process Bulk Upload/Update"):
                    with st.spinner("Executing bulk upsert..."):
                        inserted, updated, skipped = bulk_upload_csv(df)
                        
                        if inserted > 0 or updated > 0:
                            st.success(f"Bulk Operation Complete: {inserted} inserted, {updated} updated, {skipped} skipped.")
                            st.rerun() # Refresh app to see new data in the Finder tab

            except Exception as e:
                st.error(f"Error processing CSV: {e}")

# 2. Find Employee Tab (with type-ahead suggestion)
with tab_find:
    st.header("Employee Finder")
    st.info("Start typing a name in the box below to instantly filter the list and view details.")

    employee_names = get_employee_names()

    if employee_names:
        selected_name = st.selectbox(
            "Select or Type Employee Name",
            options=employee_names,
            index=None,
            placeholder="Search for an employee..."
        )

        if selected_name:
            details = get_employee_details(selected_name)
            if details:
                st.subheader(f"Details for {details['name']}")
                
                col_email, col_bday = st.columns(2)
                
                with col_email:
                    st.metric("Email", details['email'])
                
                with col_bday:
                    formatted_bday = details['birthday'].strftime("%B %d, %Y")
                    st.metric("Birthday", formatted_bday)

                st.caption(f"Last Wished Year: {details['last_wished_year']}")
            else:
                st.error("Details not found for selected employee.")
    else:
        st.warning("No employee records found. Add data using the first tab.")


# 3. Delete Employee Tab
with tab_delete:
    st.header("Delete Employee Record")
    st.error("⚠️ Warning: Deletion is permanent.")

    employee_names_del = get_employee_names()

    if employee_names_del:
        name_to_delete = st.selectbox(
            "Employee to Delete",
            options=employee_names_del,
            index=None,
            placeholder="Select an employee to remove..."
        )

        if name_to_delete:
            st.markdown(f"**Confirm Deletion:** Are you sure you want to delete **{name_to_delete}**?")
            
            if st.button(f"🔥 Yes, Permanently Delete {name_to_delete}", type="primary"):
                with st.spinner(f"Deleting {name_to_delete}..."):
                    if delete_employee(name_to_delete):
                        st.success(f"Employee **{name_to_delete}** deleted successfully!")
                        st.rerun() # Refresh UI after deletion
    else:
        st.warning("No employees available to delete.")

st.markdown("---")
st.caption("Developed with Streamlit for PostgreSQL/Neon DB.")
