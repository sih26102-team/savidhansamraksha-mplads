"""
ETL Pipeline for SavidhanSamraksha Infrastructure Records
Author: Phaneendra (Data Pipeline Lead)

Stages:
1. Extract: Ingests raw JSON/CSV data from state government portals & MPLADS feeds.
2. Transform: Validates schema, normalizes cost metrics, checks for missing data.
3. Load: Ingests transformed records into PostgreSQL database tables.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

RAW_DATA_PATH = Path(__file__).parent / "raw_data" / "sample_projects.json"

REQUIRED_FIELDS = [
    "workId", "title", "state", "district", "category",
    "estimatedCost", "sanctionedAmount", "expenditureIncurred",
    "physicalProgressPct", "dateOfSanction"
]

def extract_raw_records() -> List[Dict[str, Any]]:
    if not RAW_DATA_PATH.exists():
        print(f"[ETL Error] Raw data file {RAW_DATA_PATH} not found.")
        return []
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def transform_records(records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    cleaned = []
    for r in records:
        # Check required fields
        if not all(k in r for k in REQUIRED_FIELDS):
            print(f"[ETL Warning] Dropping incomplete record: {r.get('workId', 'NO_ID')}")
            continue
            
        sanctioned = float(r["sanctionedAmount"])
        expenditure = float(r["expenditureIncurred"])
        progress = float(r["physicalProgressPct"])
        
        # Calculate financial progress percentage
        financial_pct = round((expenditure / max(1.0, sanctioned)) * 100.0, 1)
        
        # Calculate payment divergence
        divergence = round(financial_pct - progress, 1)
        
        item = {
            **r,
            "financialProgressPct": financial_pct,
            "divergencePct": divergence,
            "isFlagged": divergence > 25.0 or r.get("dataCompleteness") == "INCOMPLETE"
        }
        cleaned.append(item)
    return cleaned

def run_etl():
    print("==================================================")
    print("   SAVIDHANSAMRAKSHA DATA ETL PIPELINE            ")
    print("==================================================")
    print("[1/3] Extracting records from raw storage...")
    raw = extract_raw_records()
    print(f"      Extracted {len(raw)} raw records.")
    
    print("[2/3] Transforming and validating schema...")
    transformed = transform_records(raw)
    print(f"      Successfully validated {len(transformed)} records.")
    
    print("[3/3] Ready for database load.")
    flagged_count = sum(1 for x in transformed if x["isFlagged"])
    print(f"      Anomaly Detection: {flagged_count} records flagged for divergence.")
    print("==================================================")

if __name__ == "__main__":
    run_etl()
