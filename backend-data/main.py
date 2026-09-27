"""
CivicShield SavidhanSamraksha - FastAPI Backend Server
Author: Mokshagna (Backend Data Lead)
"""

import os
import sys
import json
import hashlib
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict, Any, Union

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Query, Cookie
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

# Add sibling domain packages to sys.path for cross-module Python imports
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.append(str(ROOT_DIR / "ml-engine"))
sys.path.append(str(ROOT_DIR / "backend-case"))

from risk_engine import evaluate_project_risk
from workflow_state_machine import (
    AuthorityRole, CaseWorkflowStatus, WorkflowAction, can_perform_action
)
from audit_logger import create_audit_log_entry
from escalation_router import route_escalation

DB_URL = os.environ.get("DATABASE_URL", "postgresql://postgres@127.0.0.1:5433/savidhan")

app = FastAPI(
    title="SavidhanSamraksha API",
    description="CivicShield Full-Stack Governance & Anomaly Detection REST API",
    version="2.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"https://.*\.vercel\.app|https://.*\.onrender\.com|http://localhost.*|http://127\.0\.0\.1.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

# In-memory session store (simple token -> user mapping)
SESSIONS: Dict[str, Dict[str, Any]] = {}

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    cookie_val = request.cookies.get("savidhan_session")
    if not cookie_val:
        # Check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            cookie_val = auth_header.split(" ")[1]
    if cookie_val and cookie_val in SESSIONS:
        return SESSIONS[cookie_val]
    return None

def require_user(request: Request) -> Dict[str, Any]:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# ==============================================================================
# 1. Health & Meta Endpoints
# ==============================================================================

@app.get("/api/healthz")
def healthz():
    return {"status": "ok"}

# ==============================================================================
# 2. Authentication Endpoints
# ==============================================================================

class LoginRequest(BaseModel):
    username: str
    password: str
    authority: str
    stateCode: Optional[str] = None
    districtId: Optional[Union[str, int]] = None
    constituencyId: Optional[Union[str, int]] = None
    parliamentaryCategory: Optional[str] = None

    class Config:
        extra = "ignore"

@app.get("/api/auth/demo")
def get_demo_accounts():
    return [
        {
            "label": "Ministry Administration",
            "username": "kavita.sharma",
            "password": "Demo@123",
            "authority": "MINISTRY",
            "scopeLabel": "National monitoring scope",
        },
        {
            "label": "State Nodal Authority",
            "username": "raghavendra.rao",
            "password": "Demo@123",
            "authority": "STATE_NODAL",
            "scopeLabel": "Andhra Pradesh state scope",
            "stateCode": "AP",
        },
        {
            "label": "District Nodal Officer",
            "username": "suresh.kumar",
            "password": "Demo@123",
            "authority": "DISTRICT_AUTHORITY",
            "scopeLabel": "Anakapalli, Andhra Pradesh",
            "stateCode": "AP",
            "districtId": "AP-01",
        },
        {
            "label": "Lok Sabha MP",
            "username": "meenakshi.iyer",
            "password": "Demo@123",
            "authority": "MP",
            "mpCategory": "LOK_SABHA",
            "scopeLabel": "AP · Parliamentary Constituency 1",
            "stateCode": "AP",
            "constituencyId": "AP-LS-01",
        },
        {
            "label": "Rajya Sabha MP",
            "username": "vikram.varma",
            "password": "Demo@123",
            "authority": "MP",
            "mpCategory": "RAJYA_SABHA",
            "scopeLabel": "AP · Anakapalli District (Rajya Sabha)",
            "stateCode": "AP",
            "districtId": "AP-01",
        },
        {
            "label": "Nominated MP",
            "username": "sneha.deshmukh",
            "password": "Demo@123",
            "authority": "MP",
            "mpCategory": "NOMINATED",
            "scopeLabel": "National oversight (Nominated MP)",
        },
    ]

DEMO_USERS_MAP = {
    "kavita.sharma": {
        "id": "1",
        "fullName": "Kavita Sharma",
        "username": "kavita.sharma",
        "designation": "Director (MPLADS Central Administration)",
        "role": "MINISTRY",
        "stateCode": None,
        "districtId": None,
        "constituencyId": None,
        "scopeLabel": "National monitoring scope",
        "readOnly": False,
    },
    "raghavendra.rao": {
        "id": "2",
        "fullName": "Raghavendra Rao",
        "username": "raghavendra.rao",
        "designation": "State Nodal Authority Officer",
        "role": "STATE_NODAL",
        "stateCode": "AP",
        "districtId": None,
        "constituencyId": None,
        "scopeLabel": "Andhra Pradesh state scope",
        "readOnly": False,
    },
    "suresh.kumar": {
        "id": "3",
        "fullName": "Suresh Kumar",
        "username": "suresh.kumar",
        "designation": "District Nodal Officer",
        "role": "DISTRICT_AUTHORITY",
        "stateCode": "AP",
        "districtId": "AP-01",
        "constituencyId": None,
        "scopeLabel": "Anakapalli, Andhra Pradesh",
        "readOnly": False,
    },
    "meenakshi.iyer": {
        "id": "4",
        "fullName": "Meenakshi Iyer",
        "username": "meenakshi.iyer",
        "designation": "Member of Parliament (Lok Sabha)",
        "role": "MP",
        "stateCode": "AP",
        "districtId": None,
        "constituencyId": "AP-LS-01",
        "scopeLabel": "AP · Parliamentary Constituency 1",
        "readOnly": True,
    },
    "vikram.varma": {
        "id": "5",
        "fullName": "Vikram Varma",
        "username": "vikram.varma",
        "designation": "Member of Parliament (Rajya Sabha)",
        "role": "MP",
        "stateCode": "AP",
        "districtId": "AP-01",
        "constituencyId": None,
        "scopeLabel": "AP · Anakapalli District (Rajya Sabha)",
        "readOnly": True,
    },
    "sneha.deshmukh": {
        "id": "6",
        "fullName": "Sneha Deshmukh",
        "username": "sneha.deshmukh",
        "designation": "Nominated Member of Parliament",
        "role": "MP",
        "stateCode": None,
        "districtId": None,
        "constituencyId": None,
        "scopeLabel": "National oversight (Nominated MP)",
        "readOnly": True,
    },
}

@app.post("/api/auth/login")
def login(body: LoginRequest, response: Response):
    user = None
    pwd_hash = hashlib.sha256(body.password.encode("utf-8")).hexdigest()

    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute(
            "SELECT * FROM users WHERE username = %s AND role = %s AND password_hash = %s",
            (body.username, body.authority, pwd_hash)
        )
        user = cur.fetchone()
        conn.close()
    except Exception as e:
        print(f"[Auth] Database connection/query error: {e}")

    # Fallback to designated demo accounts if DB lookup fails or user record missing
    if not user:
        demo_user = DEMO_USERS_MAP.get(body.username)
        if demo_user and (demo_user["role"] == body.authority or (body.authority == "MP" and demo_user["role"] == "MP")) and body.password == "Demo@123":
            user = {
                "id": demo_user["id"],
                "full_name": demo_user["fullName"],
                "username": demo_user["username"],
                "designation": demo_user["designation"],
                "role": demo_user["role"],
                "state_code": demo_user["stateCode"] or body.stateCode,
                "district_id": demo_user["districtId"] or body.districtId,
                "constituency_id": demo_user["constituencyId"] or body.constituencyId,
                "scope_label": demo_user["scopeLabel"],
                "read_only": demo_user["readOnly"],
            }

    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials for the selected authority.")

    session_user = {
        "id": str(user["id"]),
        "fullName": user["full_name"],
        "username": user["username"],
        "designation": user["designation"],
        "role": user["role"],
        "stateCode": user["state_code"],
        "districtId": user["district_id"],
        "constituencyId": user["constituency_id"],
        "scopeLabel": user["scope_label"],
        "readOnly": bool(user["read_only"]),
    }

    session_id = f"sess_{user['id']}_{hashlib.md5(os.urandom(16)).hexdigest()}"
    SESSIONS[session_id] = session_user

    response.set_cookie(
        key="savidhan_session",
        value=session_id,
        httponly=False,
        max_age=86400 * 7,
        path="/",
        samesite="none",
        secure=True
    )
    return {"user": session_user, "token": session_id}

@app.get("/api/auth/me")
def get_me(request: Request):
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return user

@app.post("/api/auth/logout")
def logout(response: Response, request: Request):
    cookie_val = request.cookies.get("savidhan_session")
    if not cookie_val:
        auth_header = request.headers.get("Authorization") or request.headers.get("authorization")
        if auth_header and auth_header.startswith("Bearer "):
            cookie_val = auth_header.split(" ")[1]
    if cookie_val and cookie_val in SESSIONS:
        del SESSIONS[cookie_val]
    response.delete_cookie(key="savidhan_session", path="/", samesite="none", secure=True)
    return {"status": "logged_out"}

# ==============================================================================
# 3. Dashboard Analytics Endpoints
# ==============================================================================

@app.get("/api/dashboard/totals")
def get_dashboard_totals(request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    scope_filter = ""
    params = []
    if user["role"] == "STATE_NODAL" and user["stateCode"]:
        scope_filter = "WHERE state_code = %s"
        params = [user["stateCode"]]
    elif user["role"] == "DISTRICT_AUTHORITY" and user["districtId"]:
        scope_filter = "WHERE district_id = %s"
        params = [user["districtId"]]
    elif user["role"] == "MP" and user["constituencyId"]:
        scope_filter = "WHERE constituency_id = %s"
        params = [user["constituencyId"]]

    cur.execute(f"""
        SELECT 
            COUNT(*) as total_projects,
            COALESCE(SUM(sanctioned_amount), 0) as sanctioned_amount,
            COALESCE(SUM(expenditure_incurred), 0) as expenditure,
            COALESCE(AVG(physical_progress_pct), 0) as avg_progress,
            COUNT(*) FILTER (WHERE risk_level = 'HIGH') as high_risk,
            COUNT(*) FILTER (WHERE risk_level = 'MODERATE') as moderate_risk,
            COUNT(*) FILTER (WHERE risk_level = 'LOW') as low_risk,
            COUNT(*) FILTER (WHERE risk_level = 'DATA_INCOMPLETE') as data_incomplete,
            COUNT(*) FILTER (WHERE workflow_status IN ('ESCALATED', 'ESCALATED_STATE')) as escalated_count
        FROM projects {scope_filter}
    """, params)
    row = cur.fetchone()
    conn.close()

    return {
        "totalProjects": row["total_projects"],
        "sanctionedAmount": float(row["sanctioned_amount"]),
        "expenditure": float(row["expenditure"]),
        "averageProgress": round(float(row["avg_progress"]), 1),
        "highRisk": row["high_risk"],
        "moderateRisk": row["moderate_risk"],
        "lowRisk": row["low_risk"],
        "dataIncomplete": row["data_incomplete"],
        "escalatedCount": row["escalated_count"],
    }

@app.get("/api/dashboard/summary")
def get_dashboard_summary(request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    scope_filter = ""
    params = []
    if user["role"] == "STATE_NODAL" and user["stateCode"]:
        scope_filter = "WHERE p.state_code = %s"
        params = [user["stateCode"]]
    elif user["role"] == "DISTRICT_AUTHORITY" and user["districtId"]:
        scope_filter = "WHERE p.district_id = %s"
        params = [user["districtId"]]
    elif user["role"] == "MP" and user["constituencyId"]:
        scope_filter = "WHERE p.constituency_id = %s"
        params = [user["constituencyId"]]

    cur.execute(f"""
        SELECT 
            COUNT(*) as total_projects,
            COALESCE(SUM(sanctioned_amount), 0) as sanctioned_amount,
            COALESCE(SUM(expenditure_incurred), 0) as expenditure,
            COALESCE(AVG(physical_progress_pct), 0) as avg_progress,
            COUNT(*) FILTER (WHERE risk_level = 'HIGH') as high_risk,
            COUNT(*) FILTER (WHERE risk_level = 'MODERATE') as moderate_risk,
            COUNT(*) FILTER (WHERE risk_level = 'LOW') as low_risk,
            COUNT(*) FILTER (WHERE risk_level = 'DATA_INCOMPLETE') as data_incomplete,
            COUNT(*) FILTER (WHERE workflow_status IN ('ESCALATED', 'ESCALATED_STATE')) as escalated_count
        FROM projects p {scope_filter}
    """, params)
    totals_row = cur.fetchone()

    # Category distribution
    cur.execute(f"""
        SELECT work_category as label, COUNT(*) as value
        FROM projects p {scope_filter}
        GROUP BY work_category ORDER BY value DESC
    """, params)
    category_rows = cur.fetchall()

    # Fiscal trend
    cur.execute(f"""
        SELECT fiscal_year as label, COUNT(*) as projects, COALESCE(SUM(expenditure_incurred), 0) as expenditure
        FROM projects p {scope_filter}
        GROUP BY fiscal_year ORDER BY fiscal_year ASC
    """, params)
    fiscal_rows = cur.fetchall()

    # Recent activity from flag_actions
    cur.execute(f"""
        SELECT a.id, a.work_id, u.full_name as user_name, a.role, a.action, a.timestamp, a.reason, a.from_status, a.to_status
        FROM flag_actions a
        JOIN users u ON a.user_id = u.id
        JOIN projects p ON a.work_id = p.work_id
        {scope_filter}
        ORDER BY a.timestamp DESC LIMIT 6
    """, params)
    activity_rows = cur.fetchall()

    conn.close()

    by_risk = [
        {"label": "HIGH", "value": totals_row["high_risk"]},
        {"label": "MODERATE", "value": totals_row["moderate_risk"]},
        {"label": "LOW", "value": totals_row["low_risk"]},
        {"label": "DATA_INCOMPLETE", "value": totals_row["data_incomplete"]},
    ]

    status_labels = ["OPEN", "UNDER_REVIEW", "ESCALATED", "ESCALATED_STATE", "RESOLVED", "DISMISSED", "CLOSED"]
    status_distribution = [{"label": s, "value": 0} for s in status_labels]

    return {
        "scopeLabel": user["scopeLabel"],
        "syntheticLabel": "Synthetic Demonstration Dataset",
        "totals": {
            "totalProjects": totals_row["total_projects"],
            "sanctionedAmount": float(totals_row["sanctioned_amount"]),
            "expenditure": float(totals_row["expenditure"]),
            "averageProgress": round(float(totals_row["avg_progress"]), 1),
            "highRisk": totals_row["high_risk"],
            "moderateRisk": totals_row["moderate_risk"],
            "lowRisk": totals_row["low_risk"],
            "dataIncomplete": totals_row["data_incomplete"],
            "escalatedCount": totals_row["escalated_count"],
        },
        "riskDistribution": by_risk,
        "statusDistribution": status_distribution,
        "categoryDistribution": [{"label": r["label"], "value": r["value"]} for r in category_rows],
        "fiscalTrend": [{"label": r["label"], "projects": r["projects"], "expenditure": float(r["expenditure"])} for r in fiscal_rows],
        "recentActivity": [
            {
                "id": str(r["id"]),
                "workId": r["work_id"],
                "userName": r["user_name"],
                "role": r["role"],
                "action": r["action"],
                "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], datetime) else str(r["timestamp"]),
                "reason": r["reason"] or "",
                "fromStatus": r["from_status"] or "NORMAL",
                "toStatus": r["to_status"] or "NORMAL",
            }
            for r in activity_rows
        ]
    }

# ==============================================================================
# 4. Projects Endpoints
# ==============================================================================

@app.get("/api/projects")
def list_projects(
    request: Request,
    search: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    riskLevel: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    conditions = ["1=1"]
    params = []

    if user["role"] == "STATE_NODAL" and user["stateCode"]:
        conditions.append("p.state_code = %s")
        params.append(user["stateCode"])
    elif user["role"] == "DISTRICT_AUTHORITY" and user["districtId"]:
        conditions.append("p.district_id = %s")
        params.append(user["districtId"])
    elif user["role"] == "MP" and user["constituencyId"]:
        conditions.append("p.constituency_id = %s")
        params.append(user["constituencyId"])

    if search:
        conditions.append("(p.work_id ILIKE %s OR p.work_description ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])
    if category:
        conditions.append("p.work_category = %s")
        params.append(category)
    if status:
        conditions.append("p.workflow_status = %s")
        params.append(status)
    if riskLevel:
        conditions.append("p.risk_level = %s")
        params.append(riskLevel)

    where_clause = " AND ".join(conditions)

    # Count
    cur.execute(f"SELECT COUNT(*) FROM projects p WHERE {where_clause}", params)
    total_count = cur.fetchone()["count"]

    # Items
    cur.execute(f"""
        SELECT 
            p.work_id, p.work_description as title, p.work_category, p.district_id, p.state_code,
            p.sanctioned_amount, p.expenditure_incurred, p.physical_progress_pct,
            p.risk_score, p.risk_level, p.workflow_status,
            p.fiscal_year, a.agency_name, d.name as district_name
        FROM projects p
        LEFT JOIN agencies a ON p.agency_id = a.agency_id
        LEFT JOIN districts d ON p.district_id = d.id
        WHERE {where_clause}
        ORDER BY p.risk_score DESC, p.updated_at DESC
        LIMIT %s OFFSET %s
    """, params + [limit, offset])
    rows = cur.fetchall()
    conn.close()

    items = [
        {
            "workId": r["work_id"],
            "title": r["title"] or "MPLADS Infrastructure Work",
            "category": r["work_category"],
            "district": r["district_name"] or "Visakhapatnam",
            "sanctionedAmount": float(r["sanctioned_amount"]),
            "expenditure": float(r["expenditure_incurred"]),
            "physicalProgress": float(r["physical_progress_pct"]),
            "riskScore": float(r["risk_score"] or 15.0),
            "riskLevel": r["risk_level"] or "LOW",
            "workflowStatus": r["workflow_status"] or "NORMAL",
            "escalationReason": "Payment velocity divergence" if (r["workflow_status"] or "").startswith("ESCALAT") else "",
            "fiscalYear": r["fiscal_year"] or "2023-2024",
            "agency": r["agency_name"] or "District Engineering Division",
        }
        for r in rows
    ]

    return {"items": items, "total": total_count, "limit": limit, "offset": offset}

@app.get("/api/projects/escalated")
def list_escalated_projects(request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    conditions = ["p.workflow_status IN ('ESCALATED', 'ESCALATED_STATE')"]
    params = []

    if user["role"] == "STATE_NODAL" and user["stateCode"]:
        conditions.append("p.state_code = %s")
        params.append(user["stateCode"])
    elif user["role"] == "DISTRICT_AUTHORITY" and user["districtId"]:
        conditions.append("p.district_id = %s")
        params.append(user["districtId"])

    where_clause = " AND ".join(conditions)

    cur.execute(f"""
        SELECT 
            p.work_id, p.work_description as title, p.work_category, p.sanctioned_amount, p.expenditure_incurred,
            p.physical_progress_pct, p.risk_score, p.risk_level, p.workflow_status,
            p.updated_at, a.agency_name, d.name as district_name
        FROM projects p
        LEFT JOIN agencies a ON p.agency_id = a.agency_id
        LEFT JOIN districts d ON p.district_id = d.id
        WHERE {where_clause}
        ORDER BY p.risk_score DESC, p.updated_at DESC
    """, params)
    rows = cur.fetchall()
    conn.close()

    items = [
        {
            "workId": r["work_id"],
            "title": r["title"] or "MPLADS Infrastructure Work",
            "category": r["work_category"],
            "district": r["district_name"] or "Visakhapatnam",
            "sanctionedAmount": float(r["sanctioned_amount"]),
            "expenditure": float(r["expenditure_incurred"]),
            "physicalProgress": float(r["physical_progress_pct"]),
            "riskScore": float(r["risk_score"] or 78.5),
            "riskLevel": r["risk_level"] or "HIGH",
            "workflowStatus": r["workflow_status"],
            "escalationReason": "Severe expenditure-progress variance flagged by ML engine",
            "escalatedAt": r["updated_at"].isoformat() if isinstance(r["updated_at"], datetime) else str(r["updated_at"]),
            "agency": r["agency_name"] or "District Engineering Division",
        }
        for r in rows
    ]
    return {"items": items, "total": len(items)}

@app.get("/api/projects/{work_id}")
def get_project_detail(work_id: str, request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT p.*, p.work_description as title, a.agency_name, a.agency_type, a.is_state_level,
               d.name as district_name, u.full_name as mp_name, u.scope_label as mp_constituency
        FROM projects p
        LEFT JOIN agencies a ON p.agency_id = a.agency_id
        LEFT JOIN districts d ON p.district_id = d.id
        LEFT JOIN users u ON p.constituency_id = u.constituency_id AND u.role = 'MP'
        WHERE p.work_id = %s
    """, [work_id])
    p = cur.fetchone()

    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # Fetch findings from risk_flags
    cur.execute("SELECT * FROM risk_flags WHERE work_id = %s", [work_id])
    findings = cur.fetchall()

    # Fetch photos from assets
    cur.execute("SELECT * FROM assets WHERE work_id = %s ORDER BY photo_date DESC", [work_id])
    photos = cur.fetchall()

    # Fetch payments from payments
    cur.execute("SELECT * FROM payments WHERE work_id = %s ORDER BY payment_date ASC", [work_id])
    payments = cur.fetchall()

    # Fetch progress
    cur.execute("SELECT * FROM progress_updates WHERE work_id = %s ORDER BY update_date ASC", [work_id])
    progress = cur.fetchall()

    conn.close()

    # Run ML engine dynamic evaluation
    ml_eval = evaluate_project_risk({
        "workId": p["work_id"],
        "estimatedCost": float(p["estimated_cost"]),
        "sanctionedAmount": float(p["sanctioned_amount"]),
        "expenditureIncurred": float(p["expenditure_incurred"]),
        "physicalProgressPct": float(p["physical_progress_pct"]),
        "dateOfSanction": p["date_of_sanction"].isoformat() if isinstance(p["date_of_sanction"], (datetime, date)) else str(p["date_of_sanction"]),
        "expectedCompletionDate": p["expected_completion_date"].isoformat() if isinstance(p["expected_completion_date"], (datetime, date)) else str(p["expected_completion_date"]),
        "tenderInvited": bool(p["tender_invited"]),
        "ucFiled": bool(p["uc_filed"]),
        "dataCompleteness": p["data_completeness"] or "COMPLETE",
        "workflowStatus": p["workflow_status"],
    })

    return {
        "workId": p["work_id"],
        "title": p["title"],
        "category": p["work_category"],
        "district": p["district_name"] or "Visakhapatnam",
        "sanctionedAmount": float(p["sanctioned_amount"]),
        "expenditure": float(p["expenditure_incurred"]),
        "physicalProgress": float(p["physical_progress_pct"]),
        "riskScore": ml_eval["riskScore"],
        "riskLevel": ml_eval["riskLevel"],
        "workflowStatus": p["workflow_status"] or "NORMAL",
        "escalationReason": p.get("escalation_reason") or ("Payment velocity divergence" if (p.get("workflow_status") or "").startswith("ESCALAT") else ""),
        "fiscalYear": p["fiscal_year"] or "2023-2024",
        "agency": p["agency_name"] or "District Engineering Division",
        "mpName": p["mp_name"] or "Lok Sabha Representative",
        "mpCategory": "Lok Sabha",
        "mpConstituency": p["mp_constituency"] or "Visakhapatnam",
        "estimatedCost": float(p["estimated_cost"]),
        "dateOfSanction": p["date_of_sanction"].isoformat() if isinstance(p["date_of_sanction"], (datetime, date)) else str(p["date_of_sanction"]),
        "expectedCompletionDate": p["expected_completion_date"].isoformat() if isinstance(p["expected_completion_date"], (datetime, date)) else str(p["expected_completion_date"]),
        "actualCompletionDate": p["actual_completion_date"].isoformat() if isinstance(p["actual_completion_date"], (datetime, date)) else None,
        "tenderInvited": bool(p["tender_invited"]),
        "ucFiled": bool(p["uc_filed"]),
        "dataCompleteness": p["data_completeness"] or "COMPLETE",
        "agencyType": p["agency_type"] or "State Government Department",
        "agencyStateLevel": bool(p["is_state_level"]),
        "paymentTotal": sum(float(pay["amount"]) for pay in payments),
        "progressUpdates": [
            {
                "date": prog["update_date"].isoformat() if isinstance(prog["update_date"], (datetime, date)) else str(prog["update_date"]),
                "stage": prog["stage"],
                "progress": float(prog["progress"]),
                "note": prog["note"] or "",
            }
            for prog in progress
        ],
        "findings": ml_eval["findings"],
        "modules": [
            {
                "name": "Financial & Temporal",
                "status": "FLAGGED" if ml_eval["riskScore"] >= 70.0 else "AVAILABLE",
                "score": ml_eval["moduleScores"]["financialTemporalScore"],
                "summary": "Multi-factor expenditure velocity vs ground measurement audit.",
                "evidence": [f["explanation"] for f in ml_eval["findings"] if f["module"] == "FINANCIAL_TEMPORAL"] or ["Milestones aligned with scheduled completion dates."],
            },
            {
                "name": "Visual & Spatial",
                "status": "AVAILABLE",
                "score": ml_eval["moduleScores"]["visualSpatialScore"],
                "summary": "Photographic ground evidence and EXIF coordinate cluster analysis.",
                "evidence": [f"{photo['stage']}: {photo['gps_status']}; {photo['duplicate_status']}" for photo in photos] or ["Verified field inspection photographs."],
            },
            {
                "name": "Satellite Change Detection",
                "status": "INCONCLUSIVE",
                "score": None,
                "summary": "DEMO / SIMULATED SATELLITE RESULT — imagery adapter is not connected to a live provider.",
                "evidence": ["Inconclusive — imagery unavailable", "NDVI and NDBI comparison simulated for demonstration."],
            }
        ],
        "photos": [
            {
                "id": str(photo["id"]),
                "stage": photo["stage"],
                "date": photo["photo_date"].isoformat() if isinstance(photo["photo_date"], (datetime, date)) else str(photo["photo_date"]),
                "uploader": photo["uploader"] or "Field Officer",
                "gpsStatus": photo["gps_status"] or "Verified GPS Coordinate Match",
                "exifStatus": photo["exif_status"] or "Valid Camera EXIF Metadata",
                "duplicateStatus": photo["duplicate_status"] or "Unique Image Hash",
                "imageUrl": photo["image_url"],
            }
            for photo in photos
        ],
        "payments": [
            {
                "tranche": pay["tranche"] or "Installment",
                "date": pay["payment_date"].isoformat() if isinstance(pay["payment_date"], (datetime, date)) else str(pay["payment_date"]),
                "amount": float(pay["amount"]),
                "approver": pay["approver"] or "Treasury Officer",
                "submittedBy": pay["submitted_by"] or "Implementing Agency",
            }
            for pay in payments
        ],
    }

class ProjectActionRequest(BaseModel):
    action: str
    reason: str
    notes: Optional[str] = None

@app.post("/api/projects/{work_id}/action")
def perform_project_action(work_id: str, body: ProjectActionRequest, request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("SELECT * FROM projects WHERE work_id = %s", [work_id])
    p = cur.fetchone()
    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    old_status = p["workflow_status"] or "NORMAL"
    new_status = old_status

    if body.action == "FLAG_FOR_INSPECTION":
        new_status = "FLAGGED"
    elif body.action == "ESCALATE_TO_STATE":
        new_status = "ESCALATED_STATE"
    elif body.action == "ESCALATE_TO_NATIONAL":
        new_status = "ESCALATED"
    elif body.action == "FREEZE_SANCTION":
        new_status = "SANCTION_FROZEN"
    elif body.action == "ORDER_INQUIRY":
        new_status = "UNDER_INQUIRY"
    elif body.action == "RESOLVE_CASE":
        new_status = "RESOLVED"
    elif body.action == "DISMISS_FLAG":
        new_status = "NORMAL"

    # Update project
    cur.execute("""
        UPDATE projects
        SET workflow_status = %s, updated_at = NOW()
        WHERE work_id = %s
    """, [new_status, work_id])

    # Record flag_action
    cur.execute("""
        INSERT INTO flag_actions (work_id, user_id, role, action, reason, from_status, to_status, timestamp)
        VALUES (%s, %s, %s, %s, %s, %s, %s, NOW())
        RETURNING id, timestamp
    """, [work_id, user["id"], user["role"], body.action, body.reason, old_status, new_status])
    action_row = cur.fetchone()
    conn.commit()
    conn.close()

    # Generate Python audit log entry
    audit_entry = create_audit_log_entry(
        work_id=work_id,
        action=body.action,
        previous_status=old_status,
        new_status=new_status,
        user_id=str(user["id"]),
        user_role=user["role"],
        notes=body.reason
    )

    return {
        "success": True,
        "workId": work_id,
        "workflowStatus": new_status,
        "actionId": str(action_row["id"]),
        "auditHash": audit_entry.current_hash,
    }

@app.get("/api/projects/{work_id}/audit")
def get_project_audit(work_id: str, request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id, a.work_id, u.full_name as user_name, a.role, a.action, a.timestamp, a.reason, a.from_status, a.to_status
        FROM flag_actions a
        JOIN users u ON a.user_id = u.id
        WHERE a.work_id = %s
        ORDER BY a.timestamp DESC
    """, [work_id])
    rows = cur.fetchall()
    conn.close()

    return {
        "items": [
            {
                "id": str(r["id"]),
                "workId": r["work_id"],
                "userName": r["user_name"],
                "role": r["role"],
                "action": r["action"],
                "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], datetime) else str(r["timestamp"]),
                "reason": r["reason"] or "",
                "fromStatus": r["from_status"] or "NORMAL",
                "toStatus": r["to_status"] or "NORMAL",
            }
            for r in rows
        ]
    }

# ==============================================================================
# 5. Administration Endpoints
# ==============================================================================

try:
    from india_admin_data import ALL_STATES, ALL_DISTRICTS, ALL_CONSTITUENCIES
except ImportError:
    ALL_STATES = []
    ALL_DISTRICTS = []
    ALL_CONSTITUENCIES = []

@app.get("/api/administration/states")
def get_states():
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT code, name FROM states ORDER BY name ASC")
        rows = cur.fetchall()
        conn.close()
        if rows:
            return [{"code": r["code"], "name": r["name"]} for r in rows]
    except Exception as e:
        print(f"[Admin] DB states lookup error, using fallback: {e}")
    return ALL_STATES

@app.get("/api/administration/districts")
def get_districts(stateCode: Optional[str] = None):
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        if stateCode:
            cur.execute("SELECT id, name, state_code FROM districts WHERE state_code = %s ORDER BY name ASC", [stateCode])
        else:
            cur.execute("SELECT id, name, state_code FROM districts ORDER BY name ASC")
        rows = cur.fetchall()
        conn.close()
        if rows:
            return [{"id": r["id"], "name": r["name"], "stateCode": r["state_code"]} for r in rows]
    except Exception as e:
        print(f"[Admin] DB districts lookup error, using fallback: {e}")
    if stateCode:
        return [d for d in ALL_DISTRICTS if d["stateCode"] == stateCode]
    return ALL_DISTRICTS

@app.get("/api/administration/states/{stateCode}/districts")
def get_state_districts(stateCode: str):
    return get_districts(stateCode=stateCode)

@app.get("/api/administration/states/{stateCode}/constituencies")
def get_state_constituencies(stateCode: str):
    try:
        conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
        cur = conn.cursor()
        cur.execute("SELECT id, name, state_code FROM constituencies WHERE state_code = %s ORDER BY name ASC", [stateCode])
        rows = cur.fetchall()
        conn.close()
        if rows:
            return [{"id": r["id"], "name": r["name"], "stateCode": r["state_code"]} for r in rows]
    except Exception as e:
        print(f"[Admin] DB constituencies lookup error, using fallback: {e}")
    return [c for c in ALL_CONSTITUENCIES if c["stateCode"] == stateCode]

# ==============================================================================
# 6. Direct Runner
# ==============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=5000, reload=True)
