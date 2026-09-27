"""
Python Database Seeder & Schema Populator
Author: Phaneendra (Data Pipeline Lead)
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

# Cross-module import to ml-engine
sys.path.append(str(Path(__file__).parent.parent / "ml-engine"))
try:
    from risk_engine import evaluate_project_risk
except ImportError:
    evaluate_project_risk = None

RAW_DATA_PATH = Path(__file__).parent / "raw_data" / "sample_projects.json"

DEMO_USERS = [
    {"email": "collector@district.gov.in", "role": "DISTRICT_AUTHORITY", "fullName": "District Collector (Visakhapatnam)", "scope": "Visakhapatnam"},
    {"email": "nodal@ap.gov.in", "role": "STATE_NODAL", "fullName": "State Nodal Officer (Andhra Pradesh)", "scope": "Andhra Pradesh"},
    {"email": "ministry@mplads.gov.in", "role": "MINISTRY", "fullName": "Central Ministry Oversight (MoSPI)", "scope": "National"},
    {"email": "mp.loksabha@parliament.in", "role": "MP", "fullName": "Lok Sabha Member of Parliament", "scope": "Visakhapatnam"},
]

def seed_data() -> Dict[str, Any]:
    print("==================================================")
    print("   SAVIDHANSAMRAKSHA PYTHON DATABASE SEEDER       ")
    print("==================================================")
    with open(RAW_DATA_PATH, "r", encoding="utf-8") as f:
        projects = json.load(f)

    seeded_projects = []
    for p in projects:
        if evaluate_project_risk:
            ml_eval = evaluate_project_risk(p)
            p["riskScore"] = ml_eval["riskScore"]
            p["riskLevel"] = ml_eval["riskLevel"]
            p["findings"] = ml_eval["findings"]
            p["features"] = ml_eval["features"]
        seeded_projects.append(p)

    print(f"[Seeder] Processed {len(seeded_projects)} projects with ML scoring.")
    print(f"[Seeder] Provisioned {len(DEMO_USERS)} official governance demo users.")
    print("==================================================")
    return {
        "projects": seeded_projects,
        "users": DEMO_USERS
    }

if __name__ == "__main__":
    seed_data()
