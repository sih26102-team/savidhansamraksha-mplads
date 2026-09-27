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

from fastapi import FastAPI, Request, Response, HTTPException, Depends, Query, Cookie, UploadFile, File
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

# Phase 2: Visual Intelligence Engine (graceful import — won't crash if libs absent)
try:
    from visual_engine import analyse_photo_upload
    _VISUAL_ENGINE_AVAILABLE = True
except ImportError:
    _VISUAL_ENGINE_AVAILABLE = False
    def analyse_photo_upload(*args, **kwargs):
        return {
            "photo_hash": None, "sha256": "", "upload_channel": "STRIPPED_OR_EXTERNAL",
            "exif": {"exif_present": False, "latitude": None, "longitude": None},
            "findings": [], "gps_status": "GPS Unavailable",
            "exif_status": "Engine Unavailable", "duplicate_status": "Unique Image Hash",
        }


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

@app.on_event("startup")
def fix_sequences():
    """Reset PostgreSQL sequences so nextval() is always greater than MAX(id)."""
    try:
        conn = psycopg2.connect(DB_URL)
        cur = conn.cursor()
        tables = [
            "flag_actions",
            "project_escalations",
            "risk_flags",
            "progress_updates",
            "payments",
            "assets",
        ]
        for tbl in tables:
            try:
                cur.execute(f"SELECT pg_get_serial_sequence('{tbl}', 'id')")
                row = cur.fetchone()
                seq = row[0] if row else None
                if seq:
                    cur.execute(f"SELECT setval('{seq}', GREATEST(COALESCE((SELECT MAX(id::bigint) FROM {tbl}), 0), 1) + 10, true)")
                    print(f"[Startup] Reset sequence {seq} for {tbl}")
            except Exception as e:
                print(f"[Startup] Sequence check skipped for {tbl}: {e}")
                conn.rollback()
        conn.commit()
        conn.close()
        print("[Startup] Sequence sync completed.")
    except Exception as e:
        print(f"[Startup] Sequence fix error: {e}")

def get_db():
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    try:
        yield conn
    finally:
        conn.close()

import base64
import hmac

# Secret key for signing session tokens — stateless, survives server restarts
SESSION_SECRET = os.environ.get("SESSION_SECRET", "savidhan-default-secret-key-2024")

def _encode_session(user_data: Dict[str, Any]) -> str:
    """Encode user data as a signed base64 token (stateless)."""
    payload = json.dumps(user_data, default=str).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload).decode("utf-8")
    sig = hmac.new(SESSION_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
    return f"{payload_b64}.{sig}"

def _decode_session(token: str) -> Optional[Dict[str, Any]]:
    """Decode and verify a signed session token."""
    try:
        parts = token.rsplit(".", 1)
        if len(parts) != 2:
            return None
        payload_b64, sig = parts
        expected_sig = hmac.new(SESSION_SECRET.encode(), payload_b64.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(sig, expected_sig):
            return None
        payload = base64.urlsafe_b64decode(payload_b64.encode("utf-8")).decode("utf-8")
        return json.loads(payload)
    except Exception:
        return None

# Legacy in-memory fallback (for tokens issued before this change)
SESSIONS: Dict[str, Dict[str, Any]] = {}

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    cookie_val = request.cookies.get("savidhan_session")
    if not cookie_val:
        # Check Authorization header as fallback
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            cookie_val = auth_header.split(" ")[1]
    if not cookie_val:
        return None
    # Try stateless token first
    user = _decode_session(cookie_val)
    if user:
        return user
    # Fallback: legacy in-memory session
    if cookie_val in SESSIONS:
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

BUILD_VERSION = "2026-09-27-v4-monotonic-ids"

@app.get("/api/healthz")
def healthz():
    return {"status": "ok", "version": BUILD_VERSION}

@app.get("/api/admin/fix-db")
def fix_db_endpoint():
    """Manual trigger to inspect and reset all sequences well past MAX(id)."""
    conn = psycopg2.connect(DB_URL)
    cur = conn.cursor()
    results = {}
    for tbl in ["flag_actions", "project_escalations", "risk_flags", "progress_updates", "payments", "assets"]:
        try:
            cur.execute(f"SELECT pg_get_serial_sequence('{tbl}', 'id')")
            row = cur.fetchone()
            seq = row[0] if row else None
            cur.execute(f"SELECT COALESCE(MAX(id::bigint), 0) FROM {tbl}")
            max_id = cur.fetchone()[0]
            if seq:
                cur.execute(f"SELECT setval('{seq}', %s, true)", [max_id + 50])
                results[tbl] = {"seq": seq, "max_id": max_id, "new_seq_val": max_id + 50}
            else:
                results[tbl] = {"seq": None, "max_id": max_id}
        except Exception as e:
            results[tbl] = {"error": str(e)}
            conn.rollback()
    conn.commit()
    conn.close()
    return results

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
        "id": "MIN-REAL-01",
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
        "id": "STA-REAL-01",
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
        "id": "DST-REAL-01",
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
        "id": "MP-REAL-01",
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
        "id": "MP-REAL-02",
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
        "id": "MP-REAL-03",
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

    # Issue a stateless signed token — survives server restarts / Render redeploys
    session_token = _encode_session(session_user)

    response.set_cookie(
        key="savidhan_session",
        value=session_token,
        httponly=False,
        max_age=86400 * 7,
        path="/",
        samesite="none",
        secure=True
    )
    return {"user": session_user, "token": session_token}

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
        SELECT a.id, a.work_id, COALESCE(u.full_name, a.user_id, 'Authority Officer') as user_name, a.role, a.action, a.timestamp, a.reason, a.from_status, a.to_status
        FROM flag_actions a
        LEFT JOIN users u ON a.user_id = u.id OR a.user_id = u.username
        JOIN projects p ON a.work_id = p.work_id
        {scope_filter}
        ORDER BY a.timestamp DESC LIMIT 6
    """, params)
    activity_rows = cur.fetchall()

    # Workflow status distribution (dynamic aggregation from scoped project records)
    cur.execute(f"""
        SELECT COALESCE(UPPER(workflow_status), 'OPEN') as ws, COUNT(*) as cnt
        FROM projects p {scope_filter}
        GROUP BY COALESCE(UPPER(workflow_status), 'OPEN')
    """, params)
    status_map = {r["ws"]: r["cnt"] for r in cur.fetchall()}

    conn.close()

    by_risk = [
        {"label": "HIGH", "value": totals_row["high_risk"]},
        {"label": "MODERATE", "value": totals_row["moderate_risk"]},
        {"label": "LOW", "value": totals_row["low_risk"]},
        {"label": "DATA_INCOMPLETE", "value": totals_row["data_incomplete"]},
    ]

    status_labels = ["OPEN", "UNDER_REVIEW", "ESCALATED", "ESCALATED_STATE", "RESOLVED", "DISMISSED", "CLOSED"]
    status_distribution = [{"label": s, "value": status_map.get(s, 0)} for s in status_labels]

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
    workflowStatus: Optional[str] = None,
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
    active_status = workflowStatus or status
    if active_status:
        conditions.append("p.workflow_status = %s")
        params.append(active_status)
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
            p.fiscal_year, p.updated_at, a.agency_name, d.name as district_name
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
            "description": r["title"] or "MPLADS Infrastructure Work",
            "category": r["work_category"] or "OTHER",
            "district": r["district_name"] or "Visakhapatnam",
            "state": r["state_code"] or "AP",
            "stateCode": r["state_code"] or "AP",
            "sanctionedAmount": float(r["sanctioned_amount"] or 0),
            "expenditure": float(r["expenditure_incurred"] or 0),
            "physicalProgress": float(r["physical_progress_pct"] or 0),
            "riskScore": float(r["risk_score"] or 15.0),
            "riskLevel": r["risk_level"] or "LOW",
            "workflowStatus": r["workflow_status"] or "OPEN",
            "escalationReason": "Payment velocity divergence" if (r["workflow_status"] or "").startswith("ESCALAT") else "",
            "fiscalYear": r["fiscal_year"] or "2023-2024",
            "agency": r["agency_name"] or "District Engineering Division",
            "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") and isinstance(r["updated_at"], (datetime, date)) else (str(r["updated_at"]) if r.get("updated_at") else datetime.utcnow().isoformat()),
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
    elif user["role"] == "MP" and user["constituencyId"]:
        conditions.append("p.constituency_id = %s")
        params.append(user["constituencyId"])

    where_clause = " AND ".join(conditions)

    cur.execute(f"""
        SELECT 
            p.work_id, p.work_description as title, p.work_category, p.district_id, p.state_code,
            p.sanctioned_amount, p.expenditure_incurred,
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
            "description": r["title"] or "MPLADS Infrastructure Work",
            "category": r["work_category"] or "OTHER",
            "district": r["district_name"] or "Visakhapatnam",
            "state": r["state_code"] or "AP",
            "stateCode": r["state_code"] or "AP",
            "sanctionedAmount": float(r["sanctioned_amount"] or 0),
            "expenditure": float(r["expenditure_incurred"] or 0),
            "physicalProgress": float(r["physical_progress_pct"] or 0),
            "riskScore": float(r["risk_score"] or 78.5),
            "riskLevel": r["risk_level"] or "HIGH",
            "workflowStatus": r["workflow_status"] or "ESCALATED",
            "escalatedByUserName": "Suresh Kumar (District Officer)" if r["workflow_status"] == "ESCALATED" else "Raghavendra Rao (State Nodal)",
            "escalatedByRole": "DISTRICT_AUTHORITY" if r["workflow_status"] == "ESCALATED" else "STATE_NODAL",
            "escalationReason": "Severe expenditure-progress variance flagged by ML engine",
            "escalatedAt": r["updated_at"].isoformat() if r.get("updated_at") and isinstance(r["updated_at"], (datetime, date)) else (str(r["updated_at"]) if r.get("updated_at") else datetime.utcnow().isoformat()),
            "updatedAt": r["updated_at"].isoformat() if r.get("updated_at") and isinstance(r["updated_at"], (datetime, date)) else (str(r["updated_at"]) if r.get("updated_at") else datetime.utcnow().isoformat()),
            "agency": r["agency_name"] or "District Engineering Division",
        }
        for r in rows
    ]
    return items

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
        "title": p["title"] or "MPLADS Infrastructure Work",
        "description": p["title"] or "MPLADS Infrastructure Work",
        "category": p["work_category"] or "OTHER",
        "district": p["district_name"] or "Visakhapatnam",
        "state": p.get("state_code") or "AP",
        "stateCode": p.get("state_code") or "AP",
        "sanctionedAmount": float(p["sanctioned_amount"] or 0),
        "expenditure": float(p["expenditure_incurred"] or 0),
        "physicalProgress": float(p["physical_progress_pct"] or 0),
        "riskScore": ml_eval["riskScore"],
        "riskLevel": ml_eval["riskLevel"],
        "isolationForestScore": ml_eval.get("isolationForestScore"),
        "isolationForestStatus": ml_eval.get("isolationForestStatus"),
        "peerSampleCount": ml_eval.get("peerSampleCount"),
        "heuristicScore": ml_eval.get("heuristicScore"),
        "workflowStatus": p["workflow_status"] or "OPEN",
        "escalationReason": p.get("escalation_reason") or ("Payment velocity divergence" if (p.get("workflow_status") or "").startswith("ESCALAT") else ""),
        "fiscalYear": p["fiscal_year"] or "2023-2024",
        "agency": p["agency_name"] or "District Engineering Division",
        "mpName": p["mp_name"] or "Lok Sabha Representative",
        "mpCategory": "Lok Sabha",
        "mpConstituency": p["mp_constituency"] or "Visakhapatnam",
        "estimatedCost": float(p["estimated_cost"] or 0),
        "dateOfSanction": p["date_of_sanction"].isoformat() if isinstance(p["date_of_sanction"], (datetime, date)) else str(p["date_of_sanction"]),
        "expectedCompletionDate": p["expected_completion_date"].isoformat() if isinstance(p["expected_completion_date"], (datetime, date)) else str(p["expected_completion_date"]),
        "actualCompletionDate": p["actual_completion_date"].isoformat() if isinstance(p["actual_completion_date"], (datetime, date)) else None,
        "updatedAt": p["updated_at"].isoformat() if p.get("updated_at") and isinstance(p["updated_at"], (datetime, date)) else (str(p["updated_at"]) if p.get("updated_at") else datetime.utcnow().isoformat()),
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
        "findings": (function_combined := [
            *ml_eval["findings"],
            *[
                {
                    "severity": rf.get("severity") or "MODERATE",
                    "title": rf.get("title") or "Recorded Compliance Notice",
                    "explanation": rf.get("explanation") or "",
                    "evidence": rf.get("evidence") or "",
                    "module": rf.get("module") or "ADMINISTRATIVE_AUDIT",
                }
                for rf in findings
                if rf.get("title") not in {f["title"] for f in ml_eval["findings"]}
            ]
        ]),
        "modules": [
            {
                "name": "Financial & Temporal",
                "status": "FLAGGED" if any(f.get("module") == "FINANCIAL_TEMPORAL" and f.get("severity") in ("HIGH", "MODERATE") for f in function_combined) or (ml_eval["riskScore"] >= 70.0 and any(f.get("module") in ("FINANCIAL_TEMPORAL", "TEMPORAL_MONITOR") for f in function_combined)) else "AVAILABLE",
                "score": ml_eval["moduleScores"]["financialTemporalScore"],
                "summary": "Multi-factor expenditure velocity vs ground measurement audit.",
                "evidence": [f["explanation"] for f in function_combined if f["module"] in ("FINANCIAL_TEMPORAL", "TEMPORAL_MONITOR")] or ["Milestones aligned with scheduled completion dates."],
            },
            {
                "name": "Visual & Spatial",
                "status": "FLAGGED" if any(f.get("module") in ("DUPLICATE_CROSS_PROJECT_PHOTO", "DUPLICATE_SEQUENTIAL_PHOTO", "MISSING_EXIF_METADATA", "GEOFENCE_MISMATCH_ANOMALY", "VISUAL_SPATIAL") for f in function_combined) or any("OUTSIDE" in (ph.get("gps_status") or "").upper() or "DUPLICATE" in (ph.get("duplicate_status") or "").upper() for ph in photos) else "AVAILABLE",
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

# ==============================================================================
# Phase 2: Photo Upload + Visual Intelligence Engine
# ==============================================================================

@app.post("/api/projects/{work_id}/photos")
async def upload_project_photo(
    work_id: str,
    request: Request,
    file: UploadFile = File(...),
    stage: str = Query(default="PROGRESS", description="Milestone stage label"),
):
    """
    Upload a progress photograph for a project.

    Steps performed:
    1. Read image bytes
    2. analyse_photo_upload() -> pHash, EXIF GPS, duplicate check, geofence
    3. Persist result to progress_updates (photo_hash, upload_channel, exif coords)
    4. Persist visual findings to risk_flags
    5. Return analysis summary (no schema changes to existing routes)
    """
    user = require_user(request)
    image_bytes = await file.read()

    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    # Fetch project for constituency coordinates
    cur.execute("SELECT * FROM projects WHERE work_id = %s", [work_id])
    project = cur.fetchone()
    if not project:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    # Pull all stored hashes for duplicate detection
    cur.execute("SELECT work_id, photo_hash FROM progress_updates WHERE photo_hash IS NOT NULL")
    stored_hashes = [dict(r) for r in cur.fetchall()]

    # Constituency centroid (approximate from seed data — fallback to None)
    try:
        cur.execute(
            "SELECT center_lat, center_lon FROM constituencies WHERE id = %s",
            [project.get("constituency_id")]
        )
        con_row = cur.fetchone()
        const_lat = float(con_row["center_lat"]) if con_row and con_row.get("center_lat") else None
        const_lon = float(con_row["center_lon"]) if con_row and con_row.get("center_lon") else None
    except Exception:
        const_lat, const_lon = None, None

    # ---- Run Phase 2 analysis pipeline ----
    analysis = analyse_photo_upload(
        image_bytes=image_bytes,
        work_id=work_id,
        all_stored_hashes=stored_hashes,
        constituency_lat=const_lat,
        constituency_lon=const_lon,
    )

    exif = analysis.get("exif", {})

    # ---- Persist to progress_updates ----
    try:
        cur.execute("SELECT COALESCE(MAX(id::bigint), 0) + 1 AS nid FROM progress_updates")
        next_pu_id = cur.fetchone()["nid"]

        cur.execute("""
            INSERT INTO progress_updates (
                id, work_id, stage, update_date, progress, note,
                photo_hash, upload_channel,
                exif_lat, exif_lon, exif_timestamp
            )
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, [
            next_pu_id, work_id, stage,
            float(project.get("physical_progress_pct") or 0),
            f"Photo uploaded via API — stage: {stage}",
            analysis.get("photo_hash"),
            analysis.get("upload_channel", "DIRECT_UPLOAD"),
            exif.get("latitude"),
            exif.get("longitude"),
            exif.get("gps_timestamp"),
        ])

        try:
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('progress_updates','id'), %s, true)",
                [next_pu_id]
            )
        except Exception:
            pass

    except Exception as pu_err:
        print(f"[PhotoUpload] progress_updates insert error (non-fatal): {pu_err}")
        conn.rollback()

    # ---- Persist visual findings to risk_flags ----
    for finding in analysis.get("findings", []):
        try:
            cur.execute("SELECT COALESCE(MAX(id::bigint), 0) + 1 AS nid FROM risk_flags")
            next_rf_id = cur.fetchone()["nid"]

            cur.execute("""
                INSERT INTO risk_flags (
                    id, work_id, flag_type, severity, title, explanation, evidence, module, created_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
                ON CONFLICT DO NOTHING
            """, [
                next_rf_id, work_id,
                finding.get("module", "VISUAL_FLAG"),
                finding.get("severity", "MODERATE"),
                finding.get("title", ""),
                finding.get("explanation", ""),
                finding.get("evidence", ""),
                finding.get("module", "VISUAL_SPATIAL"),
            ])

            try:
                cur.execute(
                    "SELECT setval(pg_get_serial_sequence('risk_flags','id'), %s, true)",
                    [next_rf_id]
                )
            except Exception:
                pass

        except Exception as rf_err:
            print(f"[PhotoUpload] risk_flags insert error (non-fatal): {rf_err}")
            conn.rollback()

    # ---- Persist photo thumbnail record to assets ----
    try:
        cur.execute("SELECT COALESCE(MAX(id::bigint), 0) + 1 AS nid FROM assets")
        next_asset_id = cur.fetchone()["nid"]

        cur.execute("""
            INSERT INTO assets (
                id, work_id, stage, photo_date, uploader,
                gps_status, exif_status, duplicate_status, image_url
            )
            VALUES (%s, %s, %s, NOW(), %s, %s, %s, %s, %s)
            ON CONFLICT DO NOTHING
        """, [
            next_asset_id, work_id, stage,
            str(user.get("username") or user.get("id") or "Field Officer"),
            analysis.get("gps_status", "GPS Unavailable"),
            analysis.get("exif_status", "Metadata Stripped / Missing"),
            analysis.get("duplicate_status", "Unique Image Hash"),
            f"/photos/{work_id}/{analysis.get('sha256', 'unknown')[:16]}.jpg",
        ])

        try:
            cur.execute(
                "SELECT setval(pg_get_serial_sequence('assets','id'), %s, true)",
                [next_asset_id]
            )
        except Exception:
            pass

    except Exception as asset_err:
        print(f"[PhotoUpload] assets insert error (non-fatal): {asset_err}")
        conn.rollback()

    conn.commit()
    conn.close()

    # Determine aggregate visual risk level from findings
    has_high = any(f.get("severity") == "HIGH" for f in analysis.get("findings", []))
    visual_risk = "HIGH" if has_high else ("MODERATE" if analysis.get("findings") else "LOW")

    return {
        "success": True,
        "workId": work_id,
        "stage": stage,
        "photoHash": analysis.get("photo_hash"),
        "sha256": analysis.get("sha256"),
        "uploadChannel": analysis.get("upload_channel"),
        "exifPresent": exif.get("exif_present", False),
        "gpsCoordinates": (
            {"lat": exif["latitude"], "lon": exif["longitude"]}
            if exif.get("latitude") is not None else None
        ),
        "gpsStatus": analysis.get("gps_status"),
        "exifStatus": analysis.get("exif_status"),
        "duplicateStatus": analysis.get("duplicate_status"),
        "visualRiskLevel": visual_risk,
        "findings": analysis.get("findings", []),
        "visualEngineAvailable": _VISUAL_ENGINE_AVAILABLE,
    }


class ProjectActionRequest(BaseModel):
    action: str
    reason: str
    notes: Optional[str] = None

@app.post("/api/projects/{work_id}/actions")
@app.post("/api/projects/{work_id}/action")
def perform_project_action(work_id: str, body: ProjectActionRequest, request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("SELECT * FROM projects WHERE work_id = %s OR work_id ILIKE %s", [work_id, work_id])
    p = cur.fetchone()
    if not p:
        conn.close()
        raise HTTPException(status_code=404, detail="Project not found")

    old_status = p["workflow_status"] or "OPEN"
    act = (body.action or "").upper()
    role = user.get("role", "AUTHORITY")
    user_identifier = str(user.get("id") or user.get("username") or "unknown")

    if act in ("FLAG_FOR_INSPECTION", "FLAG"):
        new_status = "FLAGGED"
    elif act in ("ESCALATE_TO_STATE", "ESCALATE_STATE"):
        new_status = "ESCALATED_STATE"
    elif act in ("ESCALATE_TO_NATIONAL", "ESCALATE_NATIONAL"):
        new_status = "ESCALATED"
    elif act == "ESCALATE":
        if role == "DISTRICT_AUTHORITY":
            new_status = "ESCALATED"
        else:
            new_status = "ESCALATED_STATE"
    elif act in ("REVIEW", "ACKNOWLEDGE"):
        new_status = "UNDER_REVIEW"
    elif act in ("RESOLVE", "RESOLVE_CASE"):
        new_status = "RESOLVED"
    elif act in ("DISMISS", "DISMISS_FLAG"):
        new_status = "DISMISSED"
    elif act in ("CLOSE", "CLOSE_PROJECT"):
        new_status = "CLOSED"
    elif act in ("ORDER_INQUIRY", "INQUIRY"):
        new_status = "UNDER_INQUIRY"
    elif act in ("FREEZE_SANCTION", "FREEZE"):
        new_status = "SANCTION_FROZEN"
    else:
        new_status = act

    action_id = "1"

    # --- Main transaction: update status + audit record ---
    try:
        cur.execute("""
            UPDATE projects
            SET workflow_status = %s, updated_at = NOW()
            WHERE work_id = %s
        """, [new_status, p["work_id"]])

        # Safely determine next unique ID to completely eliminate sequence desync
        cur.execute("SELECT COALESCE(MAX(id::bigint), 0) + 1 AS next_id FROM flag_actions")
        next_action_id = cur.fetchone()["next_id"]

        cur.execute("""
            INSERT INTO flag_actions (id, work_id, user_id, role, action, reason, from_status, to_status, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            RETURNING id
        """, [next_action_id, p["work_id"], user_identifier, role, body.action, body.reason, old_status, new_status])
        action_row = cur.fetchone()
        if action_row:
            action_id = str(action_row["id"])

        try:
            cur.execute("SELECT setval(pg_get_serial_sequence('flag_actions', 'id'), %s, true)", [next_action_id])
        except Exception:
            pass

        conn.commit()
    except Exception as e:
        conn.rollback()
        conn.close()
        print(f"[Action] Core action failed: {e}")
        raise HTTPException(status_code=500, detail=f"Action failed: {str(e)}")

    conn.close()

    # --- Secondary: record escalation in separate connection (non-fatal) ---
    if new_status in ("ESCALATED", "ESCALATED_STATE"):
        try:
            esc_conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
            esc_cur = esc_conn.cursor()
            target_role = "STATE_NODAL" if new_status == "ESCALATED" else "MINISTRY"

            esc_cur.execute("SELECT COALESCE(MAX(id::bigint), 0) + 1 AS next_id FROM project_escalations")
            next_esc_id = esc_cur.fetchone()["next_id"]

            esc_cur.execute("""
                INSERT INTO project_escalations (id, work_id, escalated_by_user_id, escalated_by_role, target_role, target_scope, escalation_reason, status, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, 'PENDING', NOW())
            """, [
                next_esc_id,
                p["work_id"], user_identifier, role, target_role,
                user.get("stateCode") or "NATIONAL", body.reason
            ])
            try:
                esc_cur.execute("SELECT setval(pg_get_serial_sequence('project_escalations', 'id'), %s, true)", [next_esc_id])
            except Exception:
                pass
            esc_conn.commit()
            esc_conn.close()
        except Exception as esc_err:
            print(f"[Action] Non-fatal: escalation log failed: {esc_err}")

    # --- Audit hash (non-fatal) ---
    audit_hash = "0" * 64
    try:
        audit_entry = create_audit_log_entry(
            work_id=p["work_id"],
            action=body.action,
            previous_status=old_status,
            new_status=new_status,
            user_id=user_identifier,
            user_role=role,
            notes=body.reason
        )
        audit_hash = audit_entry.current_hash
    except Exception as e:
        print(f"[Audit] Warning generating audit entry: {e}")

    return {
        "success": True,
        "workId": p["work_id"],
        "workflowStatus": new_status,
        "actionId": action_id,
        "auditHash": audit_hash,
    }

@app.get("/api/projects/{work_id}/audit")
def get_project_audit(work_id: str, request: Request):
    user = require_user(request)
    conn = psycopg2.connect(DB_URL, cursor_factory=RealDictCursor)
    cur = conn.cursor()

    cur.execute("""
        SELECT a.id, a.work_id, COALESCE(u.full_name, a.user_id, 'Authority Officer') as user_name, a.role, a.action, a.timestamp, a.reason, a.from_status, a.to_status
        FROM flag_actions a
        LEFT JOIN users u ON a.user_id = u.id OR a.user_id = u.username
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

@app.get("/api/audit/recent")
def list_recent_audit(request: Request):
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
        SELECT a.id, a.work_id, COALESCE(u.full_name, a.user_id, 'Authority Officer') as user_name, a.role, a.action, a.timestamp, a.reason, a.from_status, a.to_status
        FROM flag_actions a
        LEFT JOIN users u ON a.user_id = u.id OR a.user_id = u.username
        JOIN projects p ON a.work_id = p.work_id
        {scope_filter}
        ORDER BY a.timestamp DESC LIMIT 10
    """, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": str(r["id"]),
            "workId": r["work_id"],
            "userName": r["user_name"],
            "role": r["role"],
            "action": r["action"],
            "timestamp": r["timestamp"].isoformat() if isinstance(r["timestamp"], (datetime, date)) else str(r["timestamp"]),
            "reason": r["reason"] or "",
            "fromStatus": r["from_status"] or "NORMAL",
            "toStatus": r["to_status"] or "NORMAL",
        }
        for r in rows
    ]

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
