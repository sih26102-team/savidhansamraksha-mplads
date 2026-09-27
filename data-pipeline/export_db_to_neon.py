"""
Export Local PostgreSQL Database to Remote Neon Cloud Database
Usage: python data-pipeline/export_db_to_neon.py '<NEON_CONNECTION_STRING>'
"""

import sys
import os
import psycopg2
from psycopg2.extras import RealDictCursor

LOCAL_DB = "postgresql://postgres@127.0.0.1:5433/savidhan"

DDL_STATEMENTS = """
CREATE TABLE IF NOT EXISTS states (
    code text PRIMARY KEY,
    name text NOT NULL,
    district_count integer DEFAULT 0
);

CREATE TABLE IF NOT EXISTS districts (
    id text PRIMARY KEY,
    name text NOT NULL,
    state_code text
);

CREATE TABLE IF NOT EXISTS constituencies (
    id text PRIMARY KEY,
    name text NOT NULL,
    state_code text
);

CREATE TABLE IF NOT EXISTS agencies (
    agency_id text PRIMARY KEY,
    agency_name text NOT NULL,
    agency_type text,
    state_code text,
    district_id text,
    is_state_level boolean DEFAULT false,
    is_active boolean DEFAULT true
);

CREATE TABLE IF NOT EXISTS users (
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
);

CREATE TABLE IF NOT EXISTS projects (
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
);

CREATE TABLE IF NOT EXISTS project_escalations (
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
);

CREATE TABLE IF NOT EXISTS risk_flags (
    id serial PRIMARY KEY,
    work_id text,
    severity text,
    title text,
    explanation text,
    evidence text,
    module text
);

CREATE TABLE IF NOT EXISTS assets (
    id serial PRIMARY KEY,
    work_id text,
    stage text,
    photo_date date,
    uploader text,
    gps_status text,
    exif_status text,
    duplicate_status text,
    image_url text
);

CREATE TABLE IF NOT EXISTS payments (
    id serial PRIMARY KEY,
    work_id text,
    tranche text,
    payment_date date,
    amount numeric,
    approver text,
    submitted_by text
);

CREATE TABLE IF NOT EXISTS progress_updates (
    id serial PRIMARY KEY,
    work_id text,
    update_date date,
    stage text,
    progress numeric,
    note text
);

CREATE TABLE IF NOT EXISTS flag_actions (
    id serial PRIMARY KEY,
    work_id text,
    user_id text,
    role text,
    action text,
    timestamp timestamptz DEFAULT NOW(),
    reason text,
    from_status text,
    to_status text
);
"""

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

def apply_schema(neon_conn):
    print("\n[Step 1] Creating database schema & tables on Neon...")
    cur = neon_conn.cursor()
    cur.execute(DDL_STATEMENTS)
    neon_conn.commit()
    print("  ✓ All 12 tables created successfully on Neon cloud database.")

def migrate(neon_url: str):
    print("==================================================")
    print("   SAVIDHANSAMRAKSHA NEON CLOUD DATABASE SEEDER   ")
    print("==================================================")
    print(f"Connecting to local DB: {LOCAL_DB}")
    local_conn = psycopg2.connect(LOCAL_DB, cursor_factory=RealDictCursor)
    local_cur = local_conn.cursor()

    print(f"Connecting to Neon Cloud DB...")
    neon_conn = psycopg2.connect(neon_url)
    neon_cur = neon_conn.cursor()

    apply_schema(neon_conn)

    print("\n[Step 2] Migrating project records and governance data...")
    for table in TABLES_ORDERED:
        local_cur.execute(f"SELECT * FROM {table}")
        rows = local_cur.fetchall()
        if not rows:
            print(f"  {table}: 0 records (skipped).")
            continue

        print(f"  Migrating {table} ({len(rows)} records)...")
        col_names = list(rows[0].keys())
        col_placeholders = ", ".join(["%s"] * len(col_names))
        col_str = ", ".join([f'"{c}"' for c in col_names])

        try:
            neon_cur.execute(f'TRUNCATE TABLE "{table}" CASCADE;')
            neon_conn.commit()
        except Exception:
            neon_conn.rollback()

        insert_sql = f'INSERT INTO "{table}" ({col_str}) VALUES ({col_placeholders}) ON CONFLICT DO NOTHING'
        
        batch = []
        for r in rows:
            batch.append([r[c] for c in col_names])
            if len(batch) >= 500:
                neon_cur.executemany(insert_sql, batch)
                neon_conn.commit()
                batch = []

        if batch:
            neon_cur.executemany(insert_sql, batch)
            neon_conn.commit()

        print(f"  ✓ {table}: {len(rows)} records transferred.")

    local_conn.close()
    neon_conn.close()
    print("\n==================================================")
    print("   NEON CLOUD DATABASE SEEDING COMPLETED (100%)   ")
    print("==================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing Neon Database URL.")
        print('Usage: python data-pipeline/export_db_to_neon.py \'<NEON_CONNECTION_STRING>\'')
        sys.exit(1)
    migrate(sys.argv[1])
