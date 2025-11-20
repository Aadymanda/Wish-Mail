🎂 Automated Birthday Wishing System

This repository hosts a robust, serverless system designed to automatically manage employee records and send birthday wishes precisely at 12:01 AM IST every day, leveraging Neon PostgreSQL, Streamlit for the Admin UI, and GitHub Actions for automated scheduling.

🚀 Live Application

The Employee Admin Panel (the frontend UI) is hosted on Streamlit Cloud:

Admin UI URL: wishapp.streamlit.app

🛠️ Architecture and Technology Stack

Component

File/Service

Function

Database

Neon DB (PostgreSQL)

Securely stores employee name, email, and birthday records.

Admin UI

index.py

A Streamlit application used for manually adding, searching, updating, and deleting employee data.

Scheduler

app.py

The background worker script that runs the daily birthday check logic.

Automation

GitHub Actions

Triggers the app.py scheduler script automatically every day.

Host

Streamlit Cloud

Hosts the Admin UI (index.py).

📂 Project Structure

├── .github/workflows/
│   └── scheduler.yml         # Defines the cron job for the wishing script
├── .streamlit/
│   └── secrets.toml          # Securely stores the NEON_DB_URL for the UI
├── index.py                  # The Streamlit Admin UI (CRUD operations)
├── app.py                    # The core scheduler script (to be implemented)
└── requirements.txt          # Python dependencies


✨ Key Features

Precise Wishing: The scheduler (app.py) is set up via GitHub Actions to run at 18:31 UTC daily, ensuring execution at 00:01 AM IST (1 minute past midnight).

Simple Admin UI (index.py):

Add/Update: Manually add new employees or update existing ones via their unique email address.

Find: Use a type-ahead search to quickly locate employee details and check their birthday.

Delete: Permanently remove employee records from the database.

Flexible Connection: The Admin UI can connect to the live Neon DB using a manually entered URL or automatically via secrets.toml.

⚙️ Setup and Deployment

1. Database Configuration (Neon DB)

Create Database: Set up a PostgreSQL instance on Neon.

Get Connection String: Obtain the full connection URL (JDBC format).

Clean URL: Ensure you remove the problematic parameter for psycopg2 compatibility:

# Change THIS:
postgresql://user:password@host/db?sslmode=require&channel_binding=require 
# To THIS:
postgresql://user:password@host/db?sslmode=require


2. Streamlit Cloud (Admin UI Setup)

The Admin UI (index.py) is hosted here. The Streamlit environment needs access to the database.

Secrets File: Create a file named .streamlit/secrets.toml in your repository root to securely store the connection string for the Admin UI to use automatically on deployment.

[database]
url="postgresql://[USER]:[PASSWORD]@[HOST]/[DATABASE]?sslmode=require" 


Deployment: Deploy the repository to Streamlit Cloud, pointing to index.py as the main file.

3. GitHub Actions Scheduler (app.py Setup)

The scheduler must be run via a scheduled workflow in GitHub Actions.

Create Workflow: Create a file at .github/workflows/scheduler.yml.

name: Birthday Scheduler
on:
  schedule:
    # Runs every day at 18:31 UTC, which is 12:01 AM IST (00:01)
    - cron: '31 18 * * *'

jobs:
  run_wishes:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.10'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run Scheduler Script
        env:
          # IMPORTANT: Store your NEON_DB_URL as a GitHub Secret named DB_URL
          DB_URL: ${{ secrets.DB_URL }}
        run: python app.py
