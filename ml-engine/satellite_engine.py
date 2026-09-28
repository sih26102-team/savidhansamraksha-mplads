"""
Google Earth Engine (GEE) Sentinel-2 Satellite Change Detection Engine — Phase 3
Author: Kousic (ML Engine Lead) & Bharath (Platform Architect)

Dual-Mode Architecture:
1. Fast UI Mock Default (< 50ms sub-millisecond response for smooth UI demo and auditing).
2. Live GEE Production Engine (queries Copernicus Sentinel-2 Level-2A multi-spectral BOA reflectance).
3. Graceful fallback on credentials absence, quota limits, or atmospheric overcast without raising 500 errors.
"""

import os
import sys
import json
import math
import logging
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union

# Set up logging
logger = logging.getLogger("satellite_engine")
if not logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter("[%(name)s] %(levelname)s: %(message)s"))
    logger.addHandler(handler)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Dependency Import Guards
# ---------------------------------------------------------------------------

try:
    import ee
    _EE_AVAILABLE = True
except ImportError:
    ee = None
    _EE_AVAILABLE = False

try:
    from google.oauth2 import service_account
    import google.auth
    _GOOGLE_AUTH_AVAILABLE = True
except ImportError:
    service_account = None
    google = None
    _GOOGLE_AUTH_AVAILABLE = False

try:
    import shapely
    from shapely.geometry import Point, mapping
    _SHAPELY_AVAILABLE = True
except ImportError:
    shapely = None
    Point = None
    mapping = None
    _SHAPELY_AVAILABLE = False

try:
    import geojson
    _GEOJSON_AVAILABLE = True
except ImportError:
    geojson = None
    _GEOJSON_AVAILABLE = False


# ---------------------------------------------------------------------------
# Credential Path Resolution
# ---------------------------------------------------------------------------

def _resolve_credentials_path() -> Optional[str]:
    """Resolves the GEE service account JSON credentials path across working directories."""
    env_path = os.environ.get("GEE_SERVICE_ACCOUNT_KEY_PATH")
    here = os.path.dirname(os.path.abspath(__file__))
    candidates = [
        env_path,
        os.path.join(here, "credentials", "gee-service-account.json"),
        os.path.join(here, "..", "ml-engine", "credentials", "gee-service-account.json"),
        "ml-engine/credentials/gee-service-account.json",
        "credentials/gee-service-account.json",
        os.environ.get("EE_PRIVATE_KEY_FILE"),
        os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"),
    ]
    for candidate in candidates:
        if candidate and os.path.exists(candidate):
            return os.path.abspath(candidate)
    return None


# ---------------------------------------------------------------------------
# GEE Authentication & Initialization Routine (Dual-Mode)
# ---------------------------------------------------------------------------

_GEE_INITIALIZED: bool = False
_GEE_STATUS: str = "UNINITIALIZED"


def init_earth_engine(force_live: bool = False) -> bool:
    """
    Initializes Google Earth Engine with dual-mode operational support.
    
    1. If GEE_MOCK_MODE=true and force_live=False:
       Logs 'GEE running in Fast UI Mock Mode' and skips network init.
    2. If force_live=True or GEE_MOCK_MODE=false:
       Attempts to authenticate via service account JSON or default credentials.
       Logs 'Google Earth Engine authenticated successfully.' on success.
    3. Never raises unhandled exceptions.
    """
    global _GEE_INITIALIZED, _GEE_STATUS

    mock_mode = os.environ.get("GEE_MOCK_MODE", "true").lower() in ("true", "1", "yes")

    if mock_mode and not force_live:
        _GEE_INITIALIZED = False
        _GEE_STATUS = "MOCK_MODE_FAST"
        logger.info("GEE running in Fast UI Mock Mode")
        print("[Satellite Engine] GEE running in Fast UI Mock Mode")
        return False

    if not _EE_AVAILABLE:
        _GEE_INITIALIZED = False
        _GEE_STATUS = "EE_PACKAGE_UNAVAILABLE"
        logger.warning("earthengine-api package not installed. Operating in Fast UI Mock Mode.")
        return False

    key_path = _resolve_credentials_path()
    credentials = None

    if key_path and os.path.exists(key_path) and _GOOGLE_AUTH_AVAILABLE:
        try:
            with open(key_path, "r", encoding="utf-8") as f:
                raw_content = f.read().strip()

            try:
                key_dict = json.loads(raw_content)
                if isinstance(key_dict, dict) and "client_email" in key_dict and "private_key" in key_dict:
                    credentials = service_account.Credentials.from_service_account_info(
                        key_dict,
                        scopes=["https://www.googleapis.com/auth/earthengine"]
                    )
                else:
                    logger.warning(
                        f"Credentials file at '{key_path}' contains JSON but lacks private_key/client_email fields."
                    )
            except json.JSONDecodeError:
                logger.warning(
                    f"Credentials file at '{key_path}' contains raw key ID token ('{raw_content[:12]}...'), not a complete service account JSON dictionary."
                )
        except Exception as read_err:
            logger.warning(f"Error reading credentials file '{key_path}': {read_err}")

    try:
        if credentials:
            ee.Initialize(credentials=credentials)
            _GEE_INITIALIZED = True
            _GEE_STATUS = "SERVICE_ACCOUNT_INITIALIZED"
            logger.info("Google Earth Engine authenticated successfully.")
            print("[Satellite Engine] Google Earth Engine authenticated successfully.")
            return True
        else:
            # Fallback to local default / gcloud ADC or project initialization
            project_id = os.environ.get("EE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
            _GEE_INITIALIZED = True
            _GEE_STATUS = "DEFAULT_INITIALIZED"
            logger.info("Google Earth Engine authenticated successfully.")
            print("[Satellite Engine] Google Earth Engine authenticated successfully.")
            return True
    except Exception as exc:
        _GEE_INITIALIZED = False
        _GEE_STATUS = f"INIT_FAILED_{type(exc).__name__}"
        logger.warning(f"Live GEE authentication failed ({type(exc).__name__}: {exc}). Falling back to Fast UI Mock Mode.")
        if force_live:
            print(f"[Satellite Engine] Live GEE authentication failed: {exc}")
        return False


# Backward-compatible alias
initialize_earth_engine = init_earth_engine

# Eager initialization on import (respects GEE_MOCK_MODE=true default)
init_earth_engine(force_live=False)


# ---------------------------------------------------------------------------
# Helper: Parse date strings or objects
# ---------------------------------------------------------------------------

def _parse_date(val: Union[str, date, datetime, None], fallback: Optional[date] = None) -> date:
    if val is None:
        return fallback or date.today()
    if isinstance(val, datetime):
        return val.date()
    if isinstance(val, date):
        return val
    try:
        clean = str(val).split("T")[0].split(" ")[0].strip()
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return fallback or date.today()


# ---------------------------------------------------------------------------
# Fast Deterministic Mock Generator (< 50ms)
# ---------------------------------------------------------------------------

def _generate_deterministic_mock_satellite(
    lat: float,
    lon: float,
    sanction_date_obj: date,
    current_date_obj: date,
    physical_progress: Optional[float] = None,
    work_id: Optional[str] = None,
    force_cloud: bool = False,
    force_ghost: bool = False,
    force_unauthorized: bool = False,
) -> Dict[str, Any]:
    """
    Produces deterministic, instant (< 50ms) Sentinel-2 spectral indices
    and cloud cover values matching the production Phase 3 specification.
    """
    seed_str = f"{work_id or 'UNKNOWN'}_{lat:.4f}_{lon:.4f}_{sanction_date_obj}"
    seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
    hash_int = int(seed_hash[:8], 16)

    t0_date_str = (sanction_date_obj - timedelta(days=45)).isoformat()
    t1_date_str = current_date_obj.isoformat()

    progress = float(physical_progress if physical_progress is not None else 50.0)

    # Edge Case B: Simulated Persistent Cloud Cover (> 70%)
    if force_cloud or "CLOUD" in (work_id or "").upper():
        return {
            "status": "SATELLITE_DATA_UNAVAILABLE_CLOUDY",
            "ndbi_delta": 0.0,
            "ndvi_delta": 0.0,
            "t0_date": t0_date_str,
            "t1_date": t1_date_str,
            "cloud_cover_pct": round(82.0 + (hash_int % 150) / 10.0, 1),
            "satellite_score": None,
            "findings": [
                {
                    "severity": "LOW",
                    "title": "Satellite Verification Skipped (Cloud Cover)",
                    "explanation": (
                        "Satellite check bypassed due to heavy cloud cover or missing regional coverage; "
                        "falling back to visual & financial metrics."
                    ),
                    "evidence": (
                        "Copernicus Sentinel-2 cloud probability exceeds 70% threshold "
                        "across observation windows. No optical pixels available."
                    ),
                    "module": "SATELLITE_VERIFICATION_SKIPPED",
                }
            ],
            "mode": "MOCK_FAST",
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Anomaly Rule: Ghost Project (progress > 40% & NDBI delta < 0.03)
    if force_ghost or "GHOST" in (work_id or "").upper():
        ndbi_delta = round(0.005 + (hash_int % 15) / 1000.0, 3)
        ndvi_delta = round(0.001 - (hash_int % 10) / 1000.0, 3)
        cloud_pct = round(4.0 + (hash_int % 40) / 10.0, 1)
        return {
            "status": "ANOMALY_NO_GROUND_TRANSFORMATION",
            "ndbi_delta": ndbi_delta,
            "ndvi_delta": ndvi_delta,
            "t0_date": t0_date_str,
            "t1_date": t1_date_str,
            "cloud_cover_pct": cloud_pct,
            "satellite_score": 75.0,
            "findings": [
                {
                    "severity": "HIGH",
                    "title": "Zero Ground Transformation (Satellite Discrepancy)",
                    "explanation": (
                        "Satellite spectral analysis shows no physical structural modification "
                        "despite significant physical progress recorded in official registers."
                    ),
                    "evidence": (
                        f"Sentinel-2 dual-date NDBI delta is {ndbi_delta:+.3f} (< 0.03 threshold), "
                        f"while reported physical progress is {progress:.1f}%. Concrete/masonry signature absent."
                    ),
                    "module": "GHOST_PROJECT_NO_PHYSICAL_CHANGE",
                }
            ],
            "mode": "MOCK_FAST",
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Anomaly Rule: Unauthorized Construction (progress == 0% & NDBI delta > 0.18)
    if force_unauthorized or "UNAUTH" in (work_id or "").upper():
        ndbi_delta = round(0.210 + (hash_int % 30) / 1000.0, 3)
        ndvi_delta = round(-0.110 - (hash_int % 20) / 1000.0, 3)
        cloud_pct = round(5.0 + (hash_int % 30) / 10.0, 1)
        return {
            "status": "ANOMALY_UNREPORTED_CONSTRUCTION",
            "ndbi_delta": ndbi_delta,
            "ndvi_delta": ndvi_delta,
            "t0_date": t0_date_str,
            "t1_date": t1_date_str,
            "cloud_cover_pct": cloud_pct,
            "satellite_score": 68.0,
            "findings": [
                {
                    "severity": "HIGH",
                    "title": "Unreported Ground Construction Activity",
                    "explanation": (
                        "Satellite imagery detected significant physical earthworks and built-up structures "
                        "on the project site, but official records report 0.0% physical progress."
                    ),
                    "evidence": (
                        f"Sentinel-2 NDBI delta is {ndbi_delta:+.3f} indicating active ground modification, "
                        f"yet official registry records show 0.0% progress."
                    ),
                    "module": "UNAUTHORIZED_UNREPORTED_CONSTRUCTION",
                }
            ],
            "mode": "MOCK_FAST",
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Default Fast UI Mock: Realistic Sentinel-2 Values (NDBI 0.142, NDVI -0.085, Cloud 3.8%)
    ndbi_delta = 0.142
    ndvi_delta = -0.085
    cloud_pct = 3.8
    sat_score = 5.0

    return {
        "status": "VERIFIED_ACTIVE_CONSTRUCTION",
        "ndbi_delta": ndbi_delta,
        "ndvi_delta": ndvi_delta,
        "t0_date": t0_date_str,
        "t1_date": t1_date_str,
        "cloud_cover_pct": cloud_pct,
        "satellite_score": sat_score,
        "findings": [],
        "mode": "MOCK_FAST",
        "gee_mode": "DETERMINISTIC_MOCK",
    }


# ---------------------------------------------------------------------------
# Real Google Earth Engine Sentinel-2 Pipeline
# ---------------------------------------------------------------------------

def _run_real_gee_sentinel2_analysis(
    lat: float,
    lon: float,
    sanction_date_obj: date,
    current_date_obj: date,
    buffer_meters: int = 100,
    physical_progress: Optional[float] = None,
) -> Dict[str, Any]:
    """
    Executes live Sentinel-2 Level-2A multi-spectral change detection on Google Earth Engine.
    Computes NDBI & NDVI zonal means for T0 baseline vs T1 milestone observation windows.
    """
    roi = ee.Geometry.Point([lon, lat]).buffer(buffer_meters)

    # 60 days around sanction date
    t0_start = (sanction_date_obj - timedelta(days=30)).isoformat()
    t0_end = (sanction_date_obj + timedelta(days=30)).isoformat()

    # 60 days around current date
    t1_start = (current_date_obj - timedelta(days=30)).isoformat()
    t1_end = (current_date_obj + timedelta(days=30)).isoformat()

    collection = (
        ee.ImageCollection("COPERNICUS/S2_SR_HARMONIZED")
        .filterBounds(roi)
        .filter(ee.Filter.lt("CLOUDY_PIXEL_PERCENTAGE", 20))
    )

    t0_col = collection.filterDate(t0_start, t0_end)
    t1_col = collection.filterDate(t1_start, t1_end)

    t0_count = int(t0_col.size().getInfo())
    t1_count = int(t1_col.size().getInfo())

    # Edge Case B: Persistent Cloud Cover check
    if t0_count == 0 or t1_count == 0:
        return {
            "status": "SATELLITE_DATA_UNAVAILABLE_CLOUDY",
            "ndbi_delta": 0.0,
            "ndvi_delta": 0.0,
            "t0_date": t0_start,
            "t1_date": t1_end,
            "cloud_cover_pct": 85.0,
            "satellite_score": None,
            "findings": [
                {
                    "severity": "LOW",
                    "title": "Satellite Verification Skipped (Cloud Cover)",
                    "explanation": (
                        "Satellite check bypassed due to heavy cloud cover or missing regional coverage; "
                        "falling back to visual & financial metrics."
                    ),
                    "evidence": (
                        f"Zero cloud-free Sentinel-2 acquisitions found (T0 count: {t0_count}, T1 count: {t1_count}). "
                        f"Optical sensors obstructed by persistent overcast."
                    ),
                    "module": "SATELLITE_VERIFICATION_SKIPPED",
                }
            ],
            "mode": "LIVE_GEE",
            "gee_mode": "REAL",
        }

    # Multi-spectral composites: Sentinel-2 B4 (Red), B8 (NIR), B11 (SWIR)
    def compute_indices(img):
        ndvi = img.normalizedDifference(["B8", "B4"]).rename("NDVI")
        ndbi = img.normalizedDifference(["B11", "B8"]).rename("NDBI")
        return img.addBands([ndvi, ndbi])

    t0_img = compute_indices(t0_col.median())
    t1_img = compute_indices(t1_col.median())

    stats_t0 = t0_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=10,
        maxPixels=1e6,
    ).getInfo()

    stats_t1 = t1_img.reduceRegion(
        reducer=ee.Reducer.mean(),
        geometry=roi,
        scale=10,
        maxPixels=1e6,
    ).getInfo()

    ndbi_t0 = float(stats_t0.get("NDBI") or 0.0)
    ndbi_t1 = float(stats_t1.get("NDBI") or 0.0)
    ndvi_t0 = float(stats_t0.get("NDVI") or 0.0)
    ndvi_t1 = float(stats_t1.get("NDVI") or 0.0)

    ndbi_delta = round(ndbi_t1 - ndbi_t0, 3)
    ndvi_delta = round(ndvi_t1 - ndvi_t0, 3)

    avg_cloud = float(t1_col.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 5.0)

    progress = float(physical_progress if physical_progress is not None else 50.0)
    findings = []
    sat_score = 0.0

    if progress > 40.0 and ndbi_delta < 0.03:
        status = "ANOMALY_NO_GROUND_TRANSFORMATION"
        sat_score = 85.0
        findings.append({
            "severity": "HIGH",
            "title": "Zero Ground Transformation (Satellite Discrepancy)",
            "explanation": (
                "Satellite spectral analysis shows no significant physical structural change "
                "despite high physical progress claimed."
            ),
            "evidence": (
                f"Sentinel-2 dual-date NDBI delta is {ndbi_delta:+.3f} (< 0.03 threshold), "
                f"while reported progress is {progress:.1f}%. Earthworks absent."
            ),
            "module": "GHOST_PROJECT_NO_PHYSICAL_CHANGE",
        })
    elif progress == 0.0 and ndbi_delta > 0.18:
        status = "ANOMALY_UNREPORTED_CONSTRUCTION"
        sat_score = 70.0
        findings.append({
            "severity": "HIGH",
            "title": "Unreported Ground Construction Activity",
            "explanation": (
                "Satellite imagery detected significant physical earthworks on site, "
                "but project records report 0.0% physical progress."
            ),
            "evidence": (
                f"Sentinel-2 NDBI delta is {ndbi_delta:+.3f} indicating active ground modification, "
                f"yet project records show 0.0% progress."
            ),
            "module": "UNAUTHORIZED_UNREPORTED_CONSTRUCTION",
        })
    else:
        status = "VERIFIED_ACTIVE_CONSTRUCTION" if progress >= 20.0 else "BASELINE_EARLY_STAGE"
        sat_score = round(max(0.0, 10.0 - (progress / 10.0)), 1)

    return {
        "status": status,
        "ndbi_delta": ndbi_delta,
        "ndvi_delta": ndvi_delta,
        "t0_date": t0_start,
        "t1_date": t1_end,
        "cloud_cover_pct": round(avg_cloud, 1),
        "satellite_score": sat_score,
        "findings": findings,
        "mode": "LIVE_GEE",
        "gee_mode": "REAL",
    }


# ---------------------------------------------------------------------------
# Public Entry Point: analyze_satellite_ground_change()
# ---------------------------------------------------------------------------

def analyze_satellite_ground_change(
    lat: float,
    lon: float,
    sanction_date: Union[str, date, datetime],
    current_date: Optional[Union[str, date, datetime]] = None,
    buffer_meters: int = 100,
    physical_progress: Optional[float] = None,
    work_id: Optional[str] = None,
    force_live: bool = False,
    force_cloud: bool = False,
    force_ghost: bool = False,
    force_unauthorized: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrates Sentinel-2 satellite change detection for a given project coordinate.
    
    Modes:
    - Fast UI Mock Default: Instant response (< 50ms) matching Sentinel-2 specification.
    - Live GEE: Connects to Copernicus S2_SR_HARMONIZED on Google Earth Engine when
      force_live=True or GEE_MOCK_MODE=false.
    - Automatic Fallback: Catches any live GEE error/timeout gracefully without raising 500.
    """
    sanction_obj = _parse_date(sanction_date, fallback=date(2023, 1, 1))
    current_obj = _parse_date(current_date, fallback=date.today())

    # Check if live GEE should be used
    mock_mode = os.environ.get("GEE_MOCK_MODE", "true").lower() in ("true", "1", "yes")
    should_run_live = (force_live or not mock_mode)

    if should_run_live and not _GEE_INITIALIZED:
        init_earth_engine(force_live=True)

    if should_run_live and _GEE_INITIALIZED and not (force_cloud or force_ghost or force_unauthorized):
        try:
            return _run_real_gee_sentinel2_analysis(
                lat=lat,
                lon=lon,
                sanction_date_obj=sanction_obj,
                current_date_obj=current_obj,
                buffer_meters=buffer_meters,
                physical_progress=physical_progress,
            )
        except Exception as exc:
            logger.warning(f"Live GEE query failed ({exc}), falling back to deterministic mock.")

    # Return fast deterministic mock
    return _generate_deterministic_mock_satellite(
        lat=lat,
        lon=lon,
        sanction_date_obj=sanction_obj,
        current_date_obj=current_obj,
        physical_progress=physical_progress,
        work_id=work_id,
        force_cloud=force_cloud,
        force_ghost=force_ghost,
        force_unauthorized=force_unauthorized,
    )
