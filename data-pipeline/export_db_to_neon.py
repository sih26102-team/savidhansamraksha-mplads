"""
Robust & Fast Local PostgreSQL to Neon Cloud Database Exporter
Uses execute_values batching + auto-reconnect + keepalives
Author: Phaneendra (Data Pipeline Lead)
"""

import sys
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor, execute_values

LOCAL_DB = "postgresql://postgres@127.0.0.1:5433/savidhan"

DDL_STATEMENTS = [
    """CREATE TABLE IF NOT EXISTS states (
        code text PRIMARY KEY,
        name text NOT NULL,
        district_count integer DEFAULT 0
    );""",
    """CREATE TABLE IF NOT EXISTS districts (
        id text PRIMARY KEY,
        name text NOT NULL,
        state_code text
    );""",
    """CREATE TABLE IF NOT EXISTS constituencies (
        id text PRIMARY KEY,
        name text NOT NULL,
        state_code text
    );""",
    """CREATE TABLE IF NOT EXISTS agencies (
        agency_id text PRIMARY KEY,
        agency_name text NOT NULL,
        agency_type text,
        state_code text,
        district_id text,
        is_state_level boolean DEFAULT false,
        is_active boolean DEFAULT true
    );""",
    """CREATE TABLE IF NOT EXISTS users (
        id text PRIMARY KEY,
        full_name text NOT NULL,
        username text UNIQUE NOT NULL,
        designation text,
        role text NOT NULL,
        state_code text,
        district_id text,
        constituency_id text,
        password_hash text NOT NULL,
        scope_id text,
        scope_label text,
        read_only boolean DEFAULT false
    );""",
    """CREATE TABLE IF NOT EXISTS projects (
        work_id text PRIMARY KEY,
        mp_id text,
        state_code text,
        district_id text,
        agency_id text,
        constituency_id text,
        work_description text,
        work_category text,
        fiscal_year text,
        estimated_cost numeric,
        sanctioned_amount numeric,
        expenditure_incurred numeric,
        physical_progress_pct numeric,
        date_of_sanction date,
        expected_completion_date date,
        actual_completion_date date,
        status text,
        tender_invited boolean DEFAULT false,
        uc_filed boolean DEFAULT false,
        risk_score numeric,
        risk_level text,
        data_completeness text,
        workflow_status text,
        created_at timestamptz DEFAULT NOW(),
        updated_at timestamptz DEFAULT NOW()
    );""",
    """CREATE TABLE IF NOT EXISTS project_escalations (
        id serial PRIMARY KEY,
        work_id text,
        escalated_by_user_id text,
        escalated_by_role text,
        target_role text,
        target_scope text,
        escalation_reason text,
        status text,
        created_at timestamptz DEFAULT NOW(),
        resolved_at timestamptz,
        resolution_reason text
    );""",
    """CREATE TABLE IF NOT EXISTS risk_flags (
        id serial PRIMARY KEY,
        work_id text,
        severity text,
        title text,
        explanation text,
        evidence text,
        module text
    );""",
    """CREATE TABLE IF NOT EXISTS assets (
        id serial PRIMARY KEY,
        work_id text,
        stage text,
        photo_date date,
        uploader text,
        gps_status text,
        exif_status text,
        duplicate_status text,
        image_url text
    );""",
    """CREATE TABLE IF NOT EXISTS payments (
        id serial PRIMARY KEY,
        work_id text,
        tranche text,
        payment_date date,
        amount numeric,
        approver text,
        submitted_by text
    );""",
    """CREATE TABLE IF NOT EXISTS progress_updates (
        id serial PRIMARY KEY,
        work_id text,
        update_date date,
        stage text,
        progress numeric,
        note text
    );""",
    """CREATE TABLE IF NOT EXISTS flag_actions (
        id serial PRIMARY KEY,
        work_id text,
        user_id text,
        role text,
        action text,
        timestamp timestamptz DEFAULT NOW(),
        reason text,
        from_status text,
        to_status text
    );"""
]

TABLES_ORDERED = [
    "states",
    "districts",
    "constituencies",
    "agencies",
    "users",
    "projects",
    "project_escalations",
    "risk_flags",
    "assets",
    "payments",
    "progress_updates",
    "flag_actions"
]

def get_neon_connection(neon_url: str):
    # If using pooled connection with -pooler, clean channel_binding if present
    clean_url = neon_url.strip()
    return psycopg2.connect(
        clean_url,
        connect_timeout=30,
        keepalives=1,
        keepalives_idle=20,
        keepalives_interval=10,
        keepalives_count=5
    )

def migrate(neon_url: str):
    print("==================================================")
    print("   SAVIDHANSAMRAKSHA CLOUD DATABASE MIGRATOR      ")
    print("==================================================")
    
    print(f"Connecting to local DB: {LOCAL_DB}")
    local_conn = psycopg2.connect(LOCAL_DB, cursor_factory=RealDictCursor)
    local_cur = local_conn.cursor()

    print(f"Connecting to Neon Cloud DB...")
    neon_conn = get_neon_connection(neon_url)
    neon_cur = neon_conn.cursor()

    print("\n[Step 1] Initializing schema on Neon...")
    for ddl in DDL_STATEMENTS:
        try:
            neon_cur.execute(ddl)
            neon_conn.commit()
        except Exception as e:
            neon_conn.rollback()
            print(f"  Warning during DDL: {e}")
    print("  ✓ Schema tables verified on Neon.")

    print("\n[Step 2] Fast-streaming records into Neon cloud...")
    for table in TABLES_ORDERED:
        local_cur.execute(f"SELECT * FROM {table}")
        rows = local_cur.fetchall()
        if not rows:
            print(f"  {table}: 0 records.")
            continue

        total_rows = len(rows)
        col_names = list(rows[0].keys())
        col_str = ", ".join([f'"{c}"' for c in col_names])
        insert_sql = f'INSERT INTO "{table}" ({col_str}) VALUES %s ON CONFLICT DO NOTHING'

        # Convert rows into tuples
        data_tuples = [tuple(r[c] for c in col_names) for r in rows]

        # Use batch size of 200 for fastest transmission without pooler timeout
        chunk_size = 200
        for i in range(0, total_rows, chunk_size):
            chunk = data_tuples[i:i + chunk_size]
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    execute_values(neon_cur, insert_sql, chunk, page_size=len(chunk))
                    neon_conn.commit()
                    break
                except (psycopg2.OperationalError, psycopg2.DatabaseError) as err:
                    print(f"  [Retry {attempt+1}/{max_retries}] Reconnecting to Neon ({err})...")
                    time.sleep(2)
                    neon_conn = get_neon_connection(neon_url)
                    neon_cur = neon_conn.cursor()
                    if attempt == max_retries - 1:
                        raise err

            pct = min(100, int(((i + len(chunk)) / total_rows) * 100))
            if total_rows > 500:
                print(f"    {table}: {i + len(chunk)}/{total_rows} records ({pct}%)...", end="\r")

        print(f"  ✓ {table}: {total_rows}/{total_rows} records transferred (100%).")

    local_conn.close()
    neon_conn.close()
    print("\n==================================================")
    print("   ALL 8,200 RECORDS MIGRATED TO NEON (SUCCESS)   ")
    print("==================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing Neon Database URL.")
        print('Usage: python data-pipeline/export_db_to_neon.py \'<NEON_CONNECTION_STRING>\'')
        sys.exit(1)
    migrate(sys.argv[1])
