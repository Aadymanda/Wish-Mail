import streamlit as st
import psycopg2
from psycopg2 import sql
from datetime import date
import uuid # For generating unique IDs in the mock database

# --- Configuration and Initial State ---
st.set_page_config(
    page_title="Employee Admin Dashboard",
    page_icon="🏢",
    layout="centered",
    initial_sidebar_state="expanded"
)

TABLE_NAME = "employees"

# Initialize Session State for Connection and Mock Data
# These variables persist across user interactions
if 'db_conn' not in st.session_state:
    st.session_state.db_conn = None
if 'use_mock_db' not in st.session_state:
    # Start in mock mode by default
    st.session_state.use_mock_db = True
if 'mock_employees' not in st.session_state:
    # Initialize mock data for temporary testing
    st.session_state.mock_employees = [
        {"id": str(uuid.uuid4()), "name": "Alice Johnson (Mock)", "email": "alice@mock.com", "birthday": date(1990, 1, 1), "last_wished_year": 1900},
        {"id": str(uuid.uuid4()), "name": "Bob Lee (Mock)", "email": "bob@mock.com", "birthday": date(1985, 12, 25), "last_wished_year": 1900}
    ]

# --- Database Management Functions ---

@st.cache_resource(ttl=3600)
def establish_db_connection(db_url):
    """Attempts to establish and cache the PostgreSQL connection."""
    try:
        # Tries to connect to the database
        conn = psycopg2.connect(db_url)
        conn.autocommit = False 
        return conn
    except Exception:
        # Returns None on failure
        return None

def init_real_db(connection):
    """Ensures the employees table exists with the required schema."""
    cursor = connection.cursor()
    try:
        create_table_query = sql.SQL("""
            CREATE TABLE IF NOT EXISTS {} (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) NOT NULL,
                email VARCHAR(255) NOT NULL UNIQUE,
                birthday DATE NOT NULL,
                last_wished_year INT DEFAULT 1900
            );
        """).format(sql.Identifier(TABLE_NAME))
        cursor.execute(create_table_query)
        connection.commit()
    except Exception as e:
        st.error(f"Database initialization failed: {e}")
        connection.rollback()
    finally:
        cursor.close()

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
    with st.sidebar.expander("Configure Neon DB URL", expanded=st.session_state.use_mock_db):
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
                conn_attempt = establish_db_connection(db_url_input.strip())
            
            if conn_attempt:
                init_real_db(conn_attempt)
                st.session_state.db_conn = conn_attempt
                st.session_state.use_mock_db = False
                st.toast("Connection successful! Switching to Real DB mode.")
                st.rerun() # Rerun to refresh the UI status
            else:
                st.sidebar.error("Connection failed. Check your URL or firewall settings.")

# --- Unified CRUD Logic ---

# Determine current environment variables
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
            insert_query = sql.SQL("INSERT INTO {} (name, email, birthday) VALUES (%s, %s, %s)").format(sql.Identifier(TABLE_NAME))
            cursor.execute(insert_query, (name, email, birthday))
            conn.commit()
            return True
        except psycopg2.errors.UniqueViolation:
            st.error(f"Error: An employee with email '{email}' already exists.")
            conn.rollback()
            return False
        except Exception as e:
            st.error(f"Error adding employee: {e}")
            conn.rollback()
            return False
        finally:
            cursor.close()

def get_employee_names():
    """Fetches all employee names for the finder/selector."""
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
    """Fetches full details for a single employee."""
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
                return {"name": result[0], "email": result[1], "birthday": result[2], "last_wished_year": result[3]}
            return None
        except Exception as e:
            st.error(f"Error fetching details: {e}")
            return None
        finally:
            cursor.close()

def delete_employee(name):
    """Deletes an employee by name."""
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

tab_add, tab_find, tab_delete = st.tabs(["➕ Add New Employee", "🔍 Find Employee & Details", "🗑️ Delete Employee"])

# 1. Add Employee Tab
with tab_add:
    st.header("New Employee Entry")

    with st.form("add_employee_form", clear_on_submit=True):
        col_name, col_email = st.columns(2)
        with col_name:
            new_name = st.text_input("Full Name", max_chars=255, help="e.g., Emily Clark")
        with col_email:
            new_email = st.text_input("Email Address", max_chars=255, help="Must be unique.")
        
        # Birthday input with calendar widget
        new_birthday = st.date_input(
            "Birthday (Date Picker)",
            min_value=date(1900, 1, 1),
            max_value=date.today(),
            value=date(2000, 1, 1),
            help="Select the date of birth. This will be stored as YYYY-MM-DD."
        )

        submitted = st.form_submit_button("✅ Add Employee", type="primary")

        if submitted:
            if new_name and new_email:
                with st.spinner(f"Adding {new_name}..."):
                    if add_employee(new_name.strip(), new_email.strip(), new_birthday):
                        st.success(f"Successfully added {new_name}!")
                        st.balloons()
            else:
                st.warning("Please fill in the Name and Email fields.")

# 2. Find Employee Tab (with type-ahead suggestion)
with tab_find:
    st.header("Employee Finder")
    st.info("Start typing a name in the box below to instantly filter the list and view details.")

    employee_names = get_employee_names()

    if employee_names:
        # Streamlit's selectbox provides the required "suggest" functionality
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
