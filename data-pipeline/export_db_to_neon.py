"""
Export Local PostgreSQL Database to Remote Neon Cloud Database
Usage: python data-pipeline/export_db_to_neon.py "postgresql://user:pass@ep-xyz.ap-southeast-1.aws.neon.tech/neondb?sslmode=require"
"""

import sys
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

    for table in TABLES_ORDERED:
        print(f"\n[Migrating table] {table}...")
        
        # Get table definition from local DB
        local_cur.execute(f"SELECT column_name, data_type, is_nullable FROM information_schema.columns WHERE table_name = '{table}'")
        cols = local_cur.fetchall()
        if not cols:
            print(f"  Table {table} not found locally, skipping.")
            continue

        # Get rows
        local_cur.execute(f"SELECT * FROM {table}")
        rows = local_cur.fetchall()
        print(f"  Found {len(rows)} rows locally.")

        if not rows:
            continue

        # Check if table exists on Neon, if not create basic schema or insert
        col_names = list(rows[0].keys())
        col_placeholders = ", ".join(["%s"] * len(col_names))
        col_str = ", ".join([f'"{c}"' for c in col_names])

        # Truncate table on Neon if exists
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

        print(f"  Successfully migrated {len(rows)} records into Neon for table: {table}")

    local_conn.close()
    neon_conn.close()
    print("\n==================================================")
    print("   NEON CLOUD DATABASE SEEDING COMPLETED (100%)   ")
    print("==================================================")

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Error: Missing Neon Database URL.")
        print('Usage: python data-pipeline/export_db_to_neon.py "<NEON_CONNECTION_STRING>"')
        sys.exit(1)
    migrate(sys.argv[1])
