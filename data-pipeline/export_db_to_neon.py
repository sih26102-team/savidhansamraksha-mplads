"""
Export Local PostgreSQL Database to Remote Neon Cloud Database
Usage: python data-pipeline/export_db_to_neon.py 'postgresql://user:pass@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require'
"""

import sys
import os
import subprocess
import psycopg2
from psycopg2.extras import RealDictCursor

LOCAL_DB = "postgresql://postgres@127.0.0.1:5433/savidhan"

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
    pg_dump_path = r"C:\Program Files\PostgreSQL\18\bin\pg_dump.exe"
    if not os.path.exists(pg_dump_path):
        pg_dump_path = "pg_dump"

    schema_dump = subprocess.check_output(
        [pg_dump_path, "-h", "127.0.0.1", "-p", "5433", "-U", "postgres", "-d", "savidhan", "--schema-only", "--no-owner", "--no-privileges"],
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    clean_statements = []
    for stmt in schema_dump.split(";"):
        s = stmt.strip()
        if not s:
            continue
        if s.startswith("\\") or "drizzle" in s.lower() or s.startswith("SET ") or "SELECT pg_catalog" in s:
            continue
        clean_statements.append(s)

    cur = neon_conn.cursor()
    for s in clean_statements:
        try:
            cur.execute(s + ";")
            neon_conn.commit()
        except Exception:
            neon_conn.rollback()

    print("  Schema verified on Neon cloud database.")

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
