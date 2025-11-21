import os
from dotenv import load_dotenv
import sys
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from contextlib import contextmanager
from datetime import datetime
import time

load_dotenv()
# This library is required to connect to PostgreSQL (Neon).
try:
    import psycopg2
except ImportError:
    print("FATAL ERROR: psycopg2 library not found. Please install it with 'pip install psycopg2-binary'")
    sys.exit(1)

# --- 1. CONFIGURATION (Reading from Environment Variables) ---
PG_CONN_STRING = os.getenv("PG_CONN_STRING")
SMTP_SERVER = os.getenv("SMTP_SERVER", "smtp.office365.com") 
SMTP_PORT = os.getenv("SMTP_PORT", 587) 
EMAIL_USER = os.getenv("EMAIL_USER")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD") 

# --- 2. Database Connection Context Manager ---
@contextmanager
def db_connect():
    """Context manager to handle PostgreSQL connection and ensure it closes."""
    conn = None
    try:
        print("Connecting to Neon PostgreSQL database...")
        conn = psycopg2.connect(PG_CONN_STRING)
        yield conn
    except Exception as e:
        print(f"FATAL DB CONNECTION ERROR: Could not connect to database. Check PG_CONN_STRING. Error: {e}")
        raise
    finally:
        if conn:
            conn.close()
            print("Database connection closed.")


# --- 3. Email Sending Logic ---
def create_and_send_email(smtp_obj, recipient_name, recipient_email):
    """Creates and sends a single personalized birthday email."""
    
    msg = MIMEMultipart("alternative")
    msg['Subject'] = f"🎂 Happy Birthday from the Team, {recipient_name}!"
    msg['From'] = EMAIL_USER
    msg['To'] = recipient_email

    html = f"""\
    <html>
      <body style="font-family: sans-serif; background-color: #e6f7ff; padding: 20px;">
        <div style="max-width: 600px; margin: auto; background: #ffffff; padding: 25px; border-radius: 10px; border-left: 5px solid #0078d4; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
          <h1 style="color: #0078d4; text-align: center;">🎉 Happy Birthday, {recipient_name}! 🎉</h1>
          <p style="font-size: 16px; color: #333;">
            wish you a wonderful and joyful birthday!
          </p>
          <p style="font-size: 14px; color: #777; text-align: right; margin-top: 40px;">
            Best Regards,<br>
            Your Aadarsh (Sent from: {EMAIL_USER})
          </p>
        </div>
      </body>
    </html>
    """
    msg.attach(MIMEText(html, 'html'))

    try:
        smtp_obj.sendmail(EMAIL_USER, recipient_email, msg.as_string())
        return True
    except Exception as e:
        print(f"  ❌ Error sending email to {recipient_name} ({recipient_email}). Error: {e}")
        return False


# --- 4. Main Execution Logic ---
def run_birthday_wisher_demo():
    """Main function to perform the DB check, send emails, and update status."""
    if not all([PG_CONN_STRING, EMAIL_USER, EMAIL_PASSWORD]):
        print("CRITICAL: Missing required environment variables. Cannot proceed.")
        return

    today = datetime.now()
    current_year = today.year
    wishes_sent_count = 0
    
    print(f"--- Birthday Wisher DEMO Running for {today.strftime('%Y-%m-%d')} ---")
    
    try:
        with db_connect() as conn:
            cursor = conn.cursor()

            # SQL Query: Match today's day/month AND not wished this year.
            query = f"""
            SELECT id, name, email 
            FROM employees
            WHERE EXTRACT(MONTH FROM birthday) = {today.month} 
              AND EXTRACT(DAY FROM birthday) = {today.day}
              AND (last_wished_year IS NULL OR last_wished_year != {current_year});
            """
            cursor.execute(query)
            employees_to_wish = cursor.fetchall()
            
            print(f"Found {len(employees_to_wish)} employees eligible for a birthday wish today.")
            
            if not employees_to_wish:
                print("No eligible employees found. Exiting.")
                return

            # Initialize SMTP Connection (Office 365 / Outlook)
            print(f"Attempting to connect to SMTP server: {SMTP_SERVER}:{SMTP_PORT}...")
            smtp_obj = smtplib.SMTP(SMTP_SERVER, int(SMTP_PORT))
            smtp_obj.starttls() 
            smtp_obj.login(EMAIL_USER, EMAIL_PASSWORD)
            print("SMTP login successful.")

            # Process each eligible employee
            for employee_id, name, email in employees_to_wish:
                print(f"Processing employee: {name} (ID: {employee_id})")
                
                if create_and_send_email(smtp_obj, name, email):
                    # If successful, update the database record
                    update_query = """
                    UPDATE employees
                    SET last_wished_year = %s
                    WHERE id = %s;
                    """
                    cursor.execute(update_query, (current_year, employee_id))
                    wishes_sent_count += 1
                    conn.commit()
                    print(f"  DB updated for {name}.")
                else:
                    conn.rollback()
                    print(f"  DB update skipped for {name} due to email failure.")

            # Cleanup
            smtp_obj.quit()
            print("SMTP connection closed.")

    except smtplib.SMTPAuthenticationError:
        print("\nFATAL: SMTP Authentication Failed. Check EMAIL_USER and ensure EMAIL_PASSWORD is the correct App Password!")
    except Exception as e:
        print(f"\nA major error occurred: {e}")
        
    print(f"\n--- DEMO Complete ---")
    print(f"Total successful birthday wishes sent: {wishes_sent_count}")
    today = datetime.now()
    current_year = today.year
    # ...
    print(f"--- Birthday Wisher DEMO Running ---")
    print(f"System time at run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} (Assuming UTC)")
    print(f"SQL Query will look for birthdays on Month: {today.month}, Day: {today.day}")


if __name__ == "__main__":
    run_birthday_wisher_demo()
