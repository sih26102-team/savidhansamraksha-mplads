"""
CivicShield ML Engine — FastAPI Microservice Entry Point
Author: Kousic (ML Engine Lead) & Bharath (Platform Architect)

Provides REST endpoints for:
- Satellite Change Detection (Sentinel-2 GEE / Mock)
- Multi-Modal Risk Scoring Pipeline (Domain Rules + Isolation Forest + Visual + Satellite)
- Health and Engine Diagnostic Telemetry
"""

import os
import sys
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# Ensure ml-engine and repo root are in python path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from satellite_engine import (
    init_earth_engine,
    analyze_satellite_ground_change,
    _GEE_STATUS,
    _GEE_INITIALIZED,
)
from risk_engine import evaluate_project_risk


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI startup lifespan:
    Initializes Earth Engine environment (Fast Mock or Live GEE).
    """
    print("[ml-engine] Executing startup lifespan...")
    init_earth_engine()
    yield
    print("[ml-engine] Shutting down lifespan...")


app = FastAPI(
    title="CivicShield ML Inference Engine",
    description="Multi-Modal Anomaly Detection & Sentinel-2 Earth Engine API",
    version="3.0.0",
    lifespan=lifespan,
)


class SatelliteAnalysisRequest(BaseModel):
    lat: float = Field(..., example=17.6868)
    lon: float = Field(..., example=83.2185)
    sanction_date: str = Field(..., example="2023-01-15")
    current_date: Optional[str] = Field(None, example="2024-03-20")
    physical_progress: Optional[float] = Field(50.0, example=50.0)
    work_id: Optional[str] = Field("WORK-001", example="WORK-001")
    force_live: Optional[bool] = False
    force_cloud: Optional[bool] = False
    force_ghost: Optional[bool] = False
    force_unauthorized: Optional[bool] = False


class ProjectRiskRequest(BaseModel):
    workId: str
    estimatedCost: float
    sanctionedAmount: float
    expenditureIncurred: float
    physicalProgressPct: float
    dateOfSanction: str
    expectedCompletionDate: str
    tenderInvited: Optional[bool] = True
    ucFiled: Optional[bool] = False
    dataCompleteness: Optional[str] = "COMPLETE"
    workflowStatus: Optional[str] = "NORMAL"
    lat: Optional[float] = 17.6868
    lon: Optional[float] = 83.2185


@app.get("/healthz")
def health_check():
    return {
        "status": "HEALTHY",
        "service": "ml-engine",
        "version": "3.0.0-phase3-sentinel2",
        "gee_initialized": _GEE_INITIALIZED,
        "gee_status": _GEE_STATUS,
        "mock_mode": os.environ.get("GEE_MOCK_MODE", "true").lower() in ("true", "1", "yes"),
    }


@app.post("/api/satellite/analyze")
def analyze_satellite(req: SatelliteAnalysisRequest):
    try:
        return analyze_satellite_ground_change(
            lat=req.lat,
            lon=req.lon,
            sanction_date=req.sanction_date,
            current_date=req.current_date,
            physical_progress=req.physical_progress,
            work_id=req.work_id,
            force_live=bool(req.force_live),
            force_cloud=bool(req.force_cloud),
            force_ghost=bool(req.force_ghost),
            force_unauthorized=bool(req.force_unauthorized),
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/risk/evaluate")
def evaluate_risk(req: ProjectRiskRequest):
    try:
        return evaluate_project_risk(req.dict())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
