"""
Google Earth Engine (GEE) Sentinel-2 Satellite Change Detection Engine — Phase 3
Author: Kousic (ML Engine Lead) & Bharath (Platform Architect)

Integrates:
- Dual-date Sentinel-2 Level-2A (COPERNICUS/S2_SR_HARMONIZED) multi-spectral imagery
- Normalized Difference Built-up Index (NDBI): (B11 - B8) / (B11 + B8)
- Normalized Difference Vegetation Index (NDVI): (B8 - B4) / (B8 + B4)
- Transformation delta: mean(T1) - mean(T0) over 100m point buffer
- Edge Case B handling (persistent cloud cover > 70% or zero valid pixels)
- Ground transformation fraud detection:
  * GHOST_PROJECT_NO_PHYSICAL_CHANGE (progress > 40% but NDBI delta < 0.03)
  * UNAUTHORIZED_UNREPORTED_CONSTRUCTION (progress == 0% but NDBI delta > 0.18)
  * VERIFIED_ACTIVE_CONSTRUCTION (progress >= 20% and NDBI delta >= 0.03)
- Graceful mock fallback (GEE_MOCK_MODE) when GEE credentials are absent
"""

import os
import sys
import math
import hashlib
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List, Tuple, Union

# ---------------------------------------------------------------------------
# Dependency import guards
# ---------------------------------------------------------------------------

try:
    import ee
    _EE_AVAILABLE = True
except ImportError:
    ee = None
    _EE_AVAILABLE = False

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
# GEE Authentication & Initialization Routine
# ---------------------------------------------------------------------------

_GEE_INITIALIZED: bool = False
_GEE_STATUS: str = "UNINITIALIZED"


def initialize_earth_engine() -> bool:
    """
    Attempts to authenticate and initialize Google Earth Engine.
    Falls back gracefully to GEE_MOCK_MODE if credentials are missing,
    invalid, or if the environment variable GEE_MOCK_MODE=true is set.
    Never throws unhandled exceptions.
    """
    global _GEE_INITIALIZED, _GEE_STATUS

    force_mock = os.environ.get("GEE_MOCK_MODE", "").lower() in ("true", "1", "yes")
    if force_mock:
        _GEE_INITIALIZED = False
        _GEE_STATUS = "MOCK_MODE_FORCED"
        return False

    if not _EE_AVAILABLE:
        _GEE_INITIALIZED = False
        _GEE_STATUS = "EE_PACKAGE_UNAVAILABLE"
        return False

    try:
        service_account = os.environ.get("EE_SERVICE_ACCOUNT")
        key_file = os.environ.get("EE_PRIVATE_KEY_FILE") or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")

        if service_account and key_file and os.path.exists(key_file):
            credentials = ee.ServiceAccountCredentials(service_account, key_file)
            ee.Initialize(credentials)
            _GEE_INITIALIZED = True
            _GEE_STATUS = "SERVICE_ACCOUNT_INITIALIZED"
            return True
        else:
            # Try default project or user authentication
            project_id = os.environ.get("EE_PROJECT_ID") or os.environ.get("GOOGLE_CLOUD_PROJECT")
            if project_id:
                ee.Initialize(project=project_id)
            else:
                ee.Initialize()
            _GEE_INITIALIZED = True
            _GEE_STATUS = "DEFAULT_INITIALIZED"
            return True
    except Exception as exc:
        _GEE_INITIALIZED = False
        _GEE_STATUS = f"INIT_FAILED_{type(exc).__name__}"
        return False


# Attempt eager initialization once at module import
initialize_earth_engine()


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
        # ISO format strings: '2025-11-01' or '2025-11-01T00:00:00Z'
        clean = str(val).split("T")[0].split(" ")[0].strip()
        return datetime.strptime(clean, "%Y-%m-%d").date()
    except Exception:
        return fallback or date.today()


# ---------------------------------------------------------------------------
# Deterministic Mock Generator (Fallback when GEE credentials absent)
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
    Generates deterministic, scientifically realistic Sentinel-2 spectral indices
    and cloud cover values for simulation and testing when GEE API is offline.
    """
    seed_str = f"{work_id or 'UNKNOWN'}_{lat:.4f}_{lon:.4f}_{sanction_date_obj}"
    seed_hash = hashlib.sha256(seed_str.encode()).hexdigest()
    hash_int = int(seed_hash[:8], 16)

    t0_date_str = (sanction_date_obj - timedelta(days=45)).isoformat()
    t1_date_str = current_date_obj.isoformat()

    progress = float(physical_progress if physical_progress is not None else 50.0)

    # Edge Case B: Simulated Persistent Cloud Cover
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
                        f"Copernicus Sentinel-2 cloud probability exceeds 70% threshold "
                        f"across observation windows. No optical pixels available."
                    ),
                    "module": "SATELLITE_VERIFICATION_SKIPPED",
                }
            ],
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Anomaly Rule 1: Ghost Project (progress > 40% but NDBI delta < 0.03)
    if force_ghost or ("GHOST" in (work_id or "").upper()) or (progress > 40.0 and "ANOMALY" in (work_id or "").upper()):
        ndbi_delta = round(0.005 + (hash_int % 15) / 1000.0, 3)  # ~0.005 to 0.020
        ndvi_delta = round(-0.004 + (hash_int % 10) / 1000.0, 3)
        cloud_pct = round(3.5 + (hash_int % 80) / 10.0, 1)

        return {
            "status": "ANOMALY_NO_GROUND_TRANSFORMATION",
            "ndbi_delta": ndbi_delta,
            "ndvi_delta": ndvi_delta,
            "t0_date": t0_date_str,
            "t1_date": t1_date_str,
            "cloud_cover_pct": cloud_pct,
            "satellite_score": 85.0,
            "findings": [
                {
                    "severity": "HIGH",
                    "title": "Zero Ground Transformation (Satellite Discrepancy)",
                    "explanation": (
                        "Satellite spectral analysis shows no significant physical structural change "
                        "despite high physical progress claimed."
                    ),
                    "evidence": (
                        f"Sentinel-2 dual-date NDBI delta is {ndbi_delta:+.3f} (< 0.03 threshold), "
                        f"while reported physical progress is {progress:.1f}%. Earthworks and structural signatures absent."
                    ),
                    "module": "GHOST_PROJECT_NO_PHYSICAL_CHANGE",
                }
            ],
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Anomaly Rule 2: Unauthorized Unreported Activity (progress == 0% but NDBI delta > 0.18)
    if force_unauthorized or (progress == 0.0 and "UNAUTHORIZED" in (work_id or "").upper()):
        ndbi_delta = round(0.195 + (hash_int % 50) / 1000.0, 3)  # > 0.18
        ndvi_delta = round(-0.110 - (hash_int % 40) / 1000.0, 3)
        cloud_pct = round(4.0 + (hash_int % 70) / 10.0, 1)

        return {
            "status": "ANOMALY_UNREPORTED_CONSTRUCTION",
            "ndbi_delta": ndbi_delta,
            "ndvi_delta": ndvi_delta,
            "t0_date": t0_date_str,
            "t1_date": t1_date_str,
            "cloud_cover_pct": cloud_pct,
            "satellite_score": 60.0,
            "findings": [
                {
                    "severity": "MODERATE",
                    "title": "Unreported Ground Activity Detected",
                    "explanation": (
                        "Satellite spectral analysis shows significant ground transformation (NDBI delta > 0.18) "
                        "despite zero reported physical progress."
                    ),
                    "evidence": (
                        f"Sentinel-2 NDBI delta is {ndbi_delta:+.3f} indicating active ground modification, "
                        f"yet official registry records show 0.0% progress."
                    ),
                    "module": "UNAUTHORIZED_UNREPORTED_CONSTRUCTION",
                }
            ],
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    # Normal / Active Construction: NDBI delta correlates with progress
    # Progress 10% -> NDBI delta ~ +0.035; Progress 95% -> NDBI delta ~ +0.165
    ndbi_delta = round(0.030 + (progress / 100.0) * 0.135 + ((hash_int % 20) - 10) / 1000.0, 3)
    ndvi_delta = round(-0.015 - (progress / 100.0) * 0.080 + ((hash_int % 15) - 7) / 1000.0, 3)
    cloud_pct = round(2.5 + (hash_int % 95) / 10.0, 1)

    status = "VERIFIED_ACTIVE_CONSTRUCTION" if progress >= 20.0 else "BASELINE_EARLY_STAGE"
    sat_score = round(max(0.0, 10.0 - (progress / 10.0)), 1)

    return {
        "status": status,
        "ndbi_delta": ndbi_delta,
        "ndvi_delta": ndvi_delta,
        "t0_date": t0_date_str,
        "t1_date": t1_date_str,
        "cloud_cover_pct": cloud_pct,
        "satellite_score": sat_score,
        "findings": [],
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

    t0_start = (sanction_date_obj - timedelta(days=60)).isoformat()
    t0_end = sanction_date_obj.isoformat()

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

    # Cloud cover average from collection metadata
    avg_cloud = float(t1_col.aggregate_mean("CLOUDY_PIXEL_PERCENTAGE").getInfo() or 5.0)

    # Evaluate anomaly rules
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
        sat_score = 60.0
        findings.append({
            "severity": "MODERATE",
            "title": "Unreported Ground Activity Detected",
            "explanation": (
                "Satellite spectral analysis shows significant ground transformation (NDBI delta > 0.18) "
                "despite zero reported physical progress."
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
    force_cloud: bool = False,
    force_ghost: bool = False,
    force_unauthorized: bool = False,
) -> Dict[str, Any]:
    """
    Orchestrates Sentinel-2 satellite change detection for a given project coordinate.
    Executes live GEE queries if authenticated; otherwise falls back gracefully
    to the deterministic mock generator without throwing 500 errors.

    Returns dict conforming to Phase 3 specification:
    {
        "status": "VERIFIED_ACTIVE_CONSTRUCTION" | "ANOMALY_NO_GROUND_TRANSFORMATION" |
                  "ANOMALY_UNREPORTED_CONSTRUCTION" | "SATELLITE_DATA_UNAVAILABLE_CLOUDY",
        "ndbi_delta": float,
        "ndvi_delta": float,
        "t0_date": str,
        "t1_date": str,
        "cloud_cover_pct": float,
        "satellite_score": float or None,
        "findings": list of finding dicts,
        "gee_mode": "REAL" | "DETERMINISTIC_MOCK"
    }
    """
    sanction_obj = _parse_date(sanction_date, fallback=date(2023, 1, 1))
    current_obj = _parse_date(current_date, fallback=date.today())

    # If live GEE is online and not forced into mock mode, run real GEE
    if _GEE_INITIALIZED and not (force_cloud or force_ghost or force_unauthorized):
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
            # Non-fatal: if GEE throws quota, timeout, or network error, fall back to mock
            print(f"[SatelliteEngine] Live GEE query failed ({exc}), falling back to deterministic mock.")

    # Graceful deterministic fallback
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
