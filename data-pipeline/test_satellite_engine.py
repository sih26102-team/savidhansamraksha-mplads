"""
CivicShield Phase 3 Satellite Engine Validation & Dry-Run Suite
Author: Kousic (ML Engine Lead) & Bharath (Platform Architect)

Tests:
1. GEE fallback authentication & mock initialization
2. Sentinel-2 spectral delta computation (NDBI, NDVI)
3. Edge Case B: Persistent cloud cover (>70%) handling
4. Fraud Rule: GHOST_PROJECT_NO_PHYSICAL_CHANGE (progress > 40%, NDBI delta < 0.03)
5. Fraud Rule: UNAUTHORIZED_UNREPORTED_CONSTRUCTION (progress 0%, NDBI delta > 0.18)
6. Normal Case: VERIFIED_ACTIVE_CONSTRUCTION (progress >= 20%, NDBI delta >= 0.03)
7. Full pipeline: evaluate_project_risk() 50/20/15/15 hybrid synthesis
8. Schema check: satellite_verification payload structure
"""

import sys
from pathlib import Path

# Add ml-engine to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-engine"))

from satellite_engine import (
    analyze_satellite_ground_change,
    initialize_earth_engine,
    _EE_AVAILABLE,
    _GEE_INITIALIZED,
    _GEE_STATUS,
)
from risk_engine import evaluate_project_risk


def run_tests():
    print("=" * 64)
    print("  CIVICSHIELD PHASE 3 SATELLITE ENGINE VALIDATION SUITE")
    print("=" * 64)
    print(f"  earthengine-api installed : {_EE_AVAILABLE}")
    print(f"  GEE Initialized           : {_GEE_INITIALIZED}")
    print(f"  GEE Mode / Status         : {_GEE_STATUS}")
    print("=" * 64)

    passed = 0
    total = 8

    # ------------------------------------------------------------------
    # Test 1: Fallback initialization (no crash when uncredentialed)
    # ------------------------------------------------------------------
    try:
        ok = initialize_earth_engine()
        # Even if False, must not raise exception
        print("\n[PASSED] TEST-001: Graceful Earth Engine initialization check")
        print(f"         initialized={_GEE_INITIALIZED} status={_GEE_STATUS}")
        passed += 1
    except Exception as exc:
        print(f"\n[FAILED] TEST-001: Initialization crashed: {exc}")

    # ------------------------------------------------------------------
    # Test 2: Normal verified construction (Progress 65%)
    # ------------------------------------------------------------------
    try:
        res = analyze_satellite_ground_change(
            lat=17.6868,
            lon=83.2185,
            sanction_date="2025-01-15",
            physical_progress=65.0,
            work_id="TEST-VERIFIED-01",
        )
        assert res["status"] == "VERIFIED_ACTIVE_CONSTRUCTION", f"Expected VERIFIED_ACTIVE_CONSTRUCTION, got {res['status']}"
        assert res["ndbi_delta"] >= 0.03, f"Expected NDBI delta >= 0.03, got {res['ndbi_delta']}"
        assert res["ndvi_delta"] < 0.0, f"Expected negative NDVI delta (clearing), got {res['ndvi_delta']}"
        print("[PASSED] TEST-002: Normal project: VERIFIED_ACTIVE_CONSTRUCTION")
        print(f"         status={res['status']} | NDBI delta={res['ndbi_delta']:+.3f} | NDVI delta={res['ndvi_delta']:+.3f} | Cloud={res['cloud_cover_pct']}%")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-002: {exc}")

    # ------------------------------------------------------------------
    # Test 3: Edge Case B — Persistent Cloud Cover / Bad Weather
    # ------------------------------------------------------------------
    try:
        res = analyze_satellite_ground_change(
            lat=11.6234,
            lon=92.7265,
            sanction_date="2025-06-01",
            physical_progress=50.0,
            work_id="TEST-CLOUD-01",
            force_cloud=True,
        )
        assert res["status"] == "SATELLITE_DATA_UNAVAILABLE_CLOUDY", f"Expected SATELLITE_DATA_UNAVAILABLE_CLOUDY, got {res['status']}"
        assert res["cloud_cover_pct"] > 70.0, f"Expected cloud cover > 70%, got {res['cloud_cover_pct']}"
        assert res["satellite_score"] is None, f"Expected None score (no penalty), got {res['satellite_score']}"
        modules = [f["module"] for f in res["findings"]]
        assert "SATELLITE_VERIFICATION_SKIPPED" in modules, f"Expected SATELLITE_VERIFICATION_SKIPPED, got {modules}"
        print("[PASSED] TEST-003: Edge Case B: Persistent cloud cover handled safely")
        print(f"         status={res['status']} | cloud={res['cloud_cover_pct']}% | flag={modules[0]}")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-003: {exc}")

    # ------------------------------------------------------------------
    # Test 4: Fraud Rule 1 — Ghost Project (Progress 75%, NDBI < 0.03)
    # ------------------------------------------------------------------
    try:
        res = analyze_satellite_ground_change(
            lat=17.7001,
            lon=83.3002,
            sanction_date="2024-01-01",
            physical_progress=75.0,
            work_id="TEST-GHOST-01",
            force_ghost=True,
        )
        assert res["status"] == "ANOMALY_NO_GROUND_TRANSFORMATION", f"Expected ANOMALY_NO_GROUND_TRANSFORMATION, got {res['status']}"
        assert res["ndbi_delta"] < 0.03, f"Expected NDBI delta < 0.03, got {res['ndbi_delta']}"
        modules = [f["module"] for f in res["findings"]]
        assert "GHOST_PROJECT_NO_PHYSICAL_CHANGE" in modules, f"Expected GHOST_PROJECT_NO_PHYSICAL_CHANGE, got {modules}"
        print("[PASSED] TEST-004: Ghost project rule: GHOST_PROJECT_NO_PHYSICAL_CHANGE")
        print(f"         status={res['status']} | NDBI delta={res['ndbi_delta']:+.3f} | flag={modules[0]}")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-004: {exc}")

    # ------------------------------------------------------------------
    # Test 5: Fraud Rule 2 — Unauthorized Activity (Progress 0%, NDBI > 0.18)
    # ------------------------------------------------------------------
    try:
        res = analyze_satellite_ground_change(
            lat=17.7001,
            lon=83.3002,
            sanction_date="2025-01-01",
            physical_progress=0.0,
            work_id="TEST-UNAUTH-01",
            force_unauthorized=True,
        )
        assert res["status"] == "ANOMALY_UNREPORTED_CONSTRUCTION", f"Expected ANOMALY_UNREPORTED_CONSTRUCTION, got {res['status']}"
        assert res["ndbi_delta"] > 0.18, f"Expected NDBI delta > 0.18, got {res['ndbi_delta']}"
        modules = [f["module"] for f in res["findings"]]
        assert "UNAUTHORIZED_UNREPORTED_CONSTRUCTION" in modules, f"Expected UNAUTHORIZED_UNREPORTED_CONSTRUCTION, got {modules}"
        print("[PASSED] TEST-005: Unauthorized activity rule: UNAUTHORIZED_UNREPORTED_CONSTRUCTION")
        print(f"         status={res['status']} | NDBI delta={res['ndbi_delta']:+.3f} | flag={modules[0]}")

        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-005: {exc}")

    # ------------------------------------------------------------------
    # Test 6: evaluate_project_risk() Full Integration (Normal project)
    # ------------------------------------------------------------------
    try:
        project = {
            "workId": "INT-NORMAL-01",
            "estimatedCost": 3_000_000,
            "sanctionedAmount": 3_000_000,
            "expenditureIncurred": 1_500_000,
            "physicalProgressPct": 50.0,
            "dateOfSanction": "2025-01-01",
            "expectedCompletionDate": "2025-12-31",
            "tenderInvited": True,
            "ucFiled": False,
            "dataCompleteness": "COMPLETE",
        }
        eval_res = evaluate_project_risk(project)
        assert "satellite_verification" in eval_res, "satellite_verification key missing"
        assert "satelliteScore" in eval_res["moduleScores"], "satelliteScore missing from moduleScores"
        sat_ver = eval_res["satellite_verification"]
        assert "status" in sat_ver and "ndbi_delta" in sat_ver and "cloud_cover_pct" in sat_ver
        print("[PASSED] TEST-006: evaluate_project_risk() Phase 3 synthesis & schema")
        print(f"         riskScore={eval_res['riskScore']} | satScore={eval_res['moduleScores']['satelliteScore']} | satStatus={sat_ver['status']}")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-006: {exc}")

    # ------------------------------------------------------------------
    # Test 7: Ghost Project integration into evaluate_project_risk()
    # ------------------------------------------------------------------
    try:
        ghost_project = {
            "workId": "WS-GHOST-EVAL-01",
            "estimatedCost": 5_000_000,
            "sanctionedAmount": 5_000_000,
            "expenditureIncurred": 4_200_000,
            "physicalProgressPct": 70.0,
            "dateOfSanction": "2024-01-01",
            "expectedCompletionDate": "2024-12-31",
            "tenderInvited": True,
            "ucFiled": False,
            "dataCompleteness": "COMPLETE",
            "forceGhost": True,
        }
        ghost_res = evaluate_project_risk(ghost_project)
        findings_modules = [f["module"] for f in ghost_res["findings"]]
        assert "GHOST_PROJECT_NO_PHYSICAL_CHANGE" in findings_modules, f"Expected ghost flag, got {findings_modules}"
        assert ghost_res["moduleScores"]["satelliteScore"] >= 70.0, f"Expected elevated satellite score, got {ghost_res['moduleScores']['satelliteScore']}"
        print("[PASSED] TEST-007: Ghost project flag surfaced in full risk evaluation")
        print(f"         riskScore={ghost_res['riskScore']} | findings={findings_modules}")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-007: {exc}")

    # ------------------------------------------------------------------
    # Test 8: Edge Case B Dynamic Weight Re-normalization
    # ------------------------------------------------------------------
    try:
        cloud_project = {
            "workId": "WS-CLOUD-EVAL-01",
            "estimatedCost": 2_500_000,
            "sanctionedAmount": 2_500_000,
            "expenditureIncurred": 1_200_000,
            "physicalProgressPct": 52.0,
            "dateOfSanction": "2026-01-01",
            "expectedCompletionDate": "2026-12-31",
            "tenderInvited": True,
            "ucFiled": False,
            "dataCompleteness": "COMPLETE",
            "forceCloud": True,
        }
        cloud_res = evaluate_project_risk(cloud_project)
        # In cloud case, satellite score is None and no penalty is added (score must stay LOW < 35.0)
        assert cloud_res["moduleScores"]["satelliteScore"] is None, f"Expected None satellite score, got {cloud_res['moduleScores']['satelliteScore']}"
        assert cloud_res["riskLevel"] == "LOW", f"Expected LOW risk level, got {cloud_res['riskLevel']}"
        assert cloud_res["riskScore"] < 35.0, f"Expected riskScore < 35, got {cloud_res['riskScore']}"
        print("[PASSED] TEST-008: Cloud cover dynamic weight re-normalization (zero penalty)")
        print(f"         riskScore={cloud_res['riskScore']} | level={cloud_res['riskLevel']} | satScore=None")
        passed += 1
    except Exception as exc:
        print(f"[FAILED] TEST-008: {exc}")

    print("\n" + "=" * 64)
    print(f"  Summary: {passed}/{total} Tests Passed ({(passed/total)*100:.1f}%)")
    print("=" * 64)
    return passed == total


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
