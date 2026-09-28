"""
Savidhan Samraksha Validation Suite — Module A: Financial & Temporal Engine
Author: Kousic & Phaneendra

Validates all 8 core detectors across realistic cases and edge-case boundaries:
  TEST-A01: Remote/Hilly terrain resilience (no false positives with Tf allowance)
  TEST-A02: Cost-per-unit extreme outlier in standard plains
  TEST-A03: Near-duplicate work at co-located site (150m distance)
  TEST-A04: False positive guard: Same generic title in distant village (25km away)
  TEST-A05: Progress silence / dormancy on active project (>300 days)
  TEST-A06: Dormancy exclusion guard: Project on official hold (litigation / stay)
  TEST-A07: Isolation Forest cold-start guard: Small agency (<10 works) returns INSUFFICIENT_PEER_DATA
  TEST-A08: Structured ineligible category (RELIGIOUS / PRIVATE_CLUB)
  TEST-A09: Secondary keyword advisory resilience: Civic infrastructure near temple
  TEST-A10: Cross-cycle duplicate asset: Re-sanction of stalled prior-cycle project
  TEST-A11: No-tender compliance flag with structured collusion metadata
  TEST-A12: UC backlog calibration: Standalone (LOW) vs Compounded (HIGH)
"""

import sys
from pathlib import Path

# Add ml-engine to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-engine"))

from financial_temporal_engine import (
    FinancialTemporalEngine,
    haversine_distance_meters,
    fuzzy_text_similarity
)

def run_tests():
    print("=" * 65)
    print("  SAVIDHAN SAMRAKSHA MODULE A: FINANCIAL & TEMPORAL ENGINE TESTS")
    print("=" * 65)

    engine = FinancialTemporalEngine()
    passed = 0
    total = 12

    # --------------------------------------------------------------------------
    # TEST-A01: Remote/Hilly terrain cost resilience
    # --------------------------------------------------------------------------
    hilly_proj = {
        "workId": "WS-TEST-HIL-01",
        "category": "COMMUNITY_HALL",
        "district": "Alluri Sitharama Raju",  # Recognized hilly district
        "terrain": "HILLY",
        "sanctionedAmount": 5_200_000,        # Above plain median (40L), but within 1.30x Tf
    }
    peer_pool = [
        {"workId": f"P-{i}", "category": "COMMUNITY_HALL", "sanctionedAmount": 4_000_000}
        for i in range(12)
    ]
    res_a01 = engine.detect_cost_outlier(hilly_proj, peer_pool)
    assert res_a01 is None, f"Expected no flag for terrain-adjusted cost, got: {res_a01}"
    print("[PASSED] TEST-A01: Remote/Hilly terrain cost resilience (Tf = 1.30x applied, no false flag)")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A02: Cost-per-unit extreme outlier in plains
    # --------------------------------------------------------------------------
    plain_outlier = {
        "workId": "WS-TEST-OUT-02",
        "category": "COMMUNITY_HALL",
        "district": "Visakhapatnam",
        "terrain": "PLAINS",
        "sanctionedAmount": 9_800_000,        # > 2.4x plain norm of 40L
    }
    res_a02 = engine.detect_cost_outlier(plain_outlier, peer_pool)
    assert res_a02 is not None and res_a02["severity"] in ("HIGH", "MODERATE"), f"Expected cost outlier, got {res_a02}"
    print(f"[PASSED] TEST-A02: Plains cost outlier flagged (Z={res_a02['telemetry']['zScore']} sigma, severity={res_a02['severity']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A03: Near-duplicate work at co-located site (150m)
    # --------------------------------------------------------------------------
    candidate_dup = {
        "workId": "WS-NEW-DUP-01",
        "work_description": "Construction of Multipurpose Community Hall and Youth Center",
        "latitude": 17.6868,
        "longitude": 83.2185,
    }
    co_located_peer = [
        {
            "workId": "WS-EXISTING-01",
            "work_description": "Construction of Multipurpose Community Hall and Training Facility",
            "latitude": 17.6875,  # ~110m away
            "longitude": 83.2190,
        }
    ]
    res_a03 = engine.detect_near_duplicate(candidate_dup, co_located_peer)
    assert res_a03 is not None and res_a03["detector"] == "NEAR_DUPLICATE_WORK_SANCTION", f"Expected duplicate flag, got {res_a03}"
    print(f"[PASSED] TEST-A03: Near-duplicate caught (Distance={res_a03['telemetry']['distanceMeters']}m, Sim={res_a03['telemetry']['textSimilarity']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A04: False positive guard: Same generic title in distant village (25km)
    # --------------------------------------------------------------------------
    distant_peer = [
        {
            "workId": "WS-DISTANT-01",
            "work_description": "Construction of Multipurpose Community Hall and Youth Center",
            "latitude": 17.8500,  # ~25 km away
            "longitude": 83.4000,
        }
    ]
    res_a04 = engine.detect_near_duplicate(candidate_dup, distant_peer)
    assert res_a04 is None, f"Expected distant work NOT to be flagged, got {res_a04}"
    print("[PASSED] TEST-A04: False positive guard: Distant identical title (25km away) correctly NOT flagged")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A05: Progress silence / dormancy on active project (>300 days)
    # --------------------------------------------------------------------------
    dormant_proj = {
        "workId": "WS-DORMANT-01",
        "date_of_sanction": "2023-01-01T00:00:00Z",
        "updated_at": "2023-03-01T00:00:00Z",  # Over 500 days silent
        "physical_progress_pct": 20.0,
        "workflow_status": "NORMAL"
    }
    res_a05 = engine.detect_progress_silence(dormant_proj, None)
    assert res_a05 is not None and res_a05["detector"] == "PROGRESS_SILENCE_DORMANT", f"Expected dormancy flag, got {res_a05}"
    print(f"[PASSED] TEST-A05: Progress silence caught ({res_a05['telemetry']['daysSilent']} days silent)")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A06: Dormancy exclusion guard: Project on official hold (litigation / stay)
    # --------------------------------------------------------------------------
    stayed_proj = {
        "workId": "WS-STAYED-01",
        "date_of_sanction": "2023-01-01T00:00:00Z",
        "updated_at": "2023-03-01T00:00:00Z",
        "physical_progress_pct": 20.0,
        "workflow_status": "ON_HOLD",
        "on_hold_reason": "COURT_STAY_LAND_DISPUTE"
    }
    res_a06 = engine.detect_progress_silence(stayed_proj, None)
    assert res_a06 is None, f"Expected on-hold project to be excluded from dormancy check, got {res_a06}"
    print("[PASSED] TEST-A06: Dormancy exclusion guard: Court stay / on-hold project cleanly exempted")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A07: Isolation Forest cold-start guard (<10 samples -> INSUFFICIENT_PEER_DATA)
    # --------------------------------------------------------------------------
    small_agency_proj = {
        "workId": "WS-AGY-01",
        "sanctionedAmount": 3_000_000,
        "expenditureIncurred": 2_800_000,
        "physicalProgressPct": 25.0
    }
    thin_agency_pool = [small_agency_proj for _ in range(4)]  # Only 4 works
    res_a07 = engine.detect_utilization_outlier(small_agency_proj, thin_agency_pool)
    assert res_a07["status"] == "INSUFFICIENT_PEER_DATA" and res_a07["finding"] is None, f"Expected INSUFFICIENT_PEER_DATA, got {res_a07}"
    print("[PASSED] TEST-A07: Isolation Forest cold-start guard: Thin agency (<10 works) labeled INSUFFICIENT_PEER_DATA (0 penalty)")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A08: Structured ineligible category (RELIGIOUS)
    # --------------------------------------------------------------------------
    religious_proj = {
        "workId": "WS-INEL-01",
        "work_category": "RELIGIOUS",
        "title": "Construction of Mandir Pilgrimage Complex"
    }
    res_a08 = engine.detect_ineligible_category(religious_proj)
    assert res_a08 is not None and res_a08["severity"] == "HIGH", f"Expected HIGH ineligibility, got {res_a08}"
    print(f"[PASSED] TEST-A08: Structured ineligible category flagged ({res_a08['title']}, severity={res_a08['severity']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A09: Secondary keyword advisory resilience: Civic infrastructure near temple
    # --------------------------------------------------------------------------
    civic_near_temple = {
        "workId": "WS-CIVIC-01",
        "work_category": "ROADS",
        "title": "Laying of CC Road and Stormwater Drain from ZP High School to Temple Junction"
    }
    res_a09 = engine.detect_ineligible_category(civic_near_temple)
    assert res_a09 is None, f"Expected civic road near temple NOT to be flagged, got {res_a09}"
    print("[PASSED] TEST-A09: Secondary keyword resilience: Public CC road near temple recognized as legitimate civic infrastructure")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A10: Cross-cycle duplicate asset re-sanction
    # --------------------------------------------------------------------------
    current_cycle_proj = {
        "workId": "WS-2024-888",
        "fiscal_year": "2024-2025",
        "title": "Solar Powered RO Drinking Water Purification Plant at Anandapuram",
        "sanctionedAmount": 3_500_000
    }
    historical_pool = [
        {
            "workId": "WS-2022-111",
            "fiscal_year": "2022-2023",
            "title": "Solar Powered RO Drinking Water Plant in Anandapuram Village",
            "sanctionedAmount": 3_000_000,
            "physical_progress_pct": 18.0,  # Unfinished in prior cycle!
            "uc_filed": False
        }
    ]
    res_a10 = engine.detect_cross_cycle_duplicate(current_cycle_proj, historical_pool)
    assert res_a10 is not None and res_a10["detector"] == "CROSS_CYCLE_DUPLICATE_ASSET", f"Expected cross-cycle flag, got {res_a10}"
    print(f"[PASSED] TEST-A10: Cross-cycle duplicate asset caught (Prior work {res_a10['telemetry']['priorWorkId']}, {res_a10['telemetry']['priorProgress']}% completed)")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A11: No-tender compliance flag with structured collusion metadata
    # --------------------------------------------------------------------------
    no_tender_proj = {
        "workId": "WS-TENDER-01",
        "tender_invited": False,
        "sanctionedAmount": 4_200_000,
        "agency_id": "AGY-PRI-99",
        "approver_id": "COLL-OFF-04"
    }
    res_a11 = engine.detect_no_tender(no_tender_proj)
    assert res_a11 is not None and res_a11["telemetry"]["fusionCollusionEligible"] is True, f"Expected no-tender flag, got {res_a11}"
    print(f"[PASSED] TEST-A11: No-tender flag verified with structured Fusion Layer metadata (agency={res_a11['telemetry']['agencyId']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-A12: UC backlog calibration: Standalone (LOW) vs Compounded (HIGH)
    # --------------------------------------------------------------------------
    uc_proj = {
        "workId": "WS-UC-01",
        "uc_filed": False,
        "sanctionedAmount": 5_000_000,
        "expenditureIncurred": 4_000_000  # 80% spent
    }
    # Case 1: Standalone backlog
    res_a12_standalone = engine.detect_missing_uc(uc_proj, active_findings=[])
    assert res_a12_standalone is not None and res_a12_standalone["severity"] == "LOW", f"Expected LOW severity for standalone UC backlog, got {res_a12_standalone}"

    # Case 2: Compounded by cost outlier
    compounding_flags = [{"detector": "COST_PER_UNIT_OUTLIER", "severity": "HIGH"}]
    res_a12_compounded = engine.detect_missing_uc(uc_proj, active_findings=compounding_flags)
    assert res_a12_compounded is not None and res_a12_compounded["severity"] == "HIGH", f"Expected HIGH severity for compounded UC backlog, got {res_a12_compounded}"
    print(f"[PASSED] TEST-A12: UC backlog calibration: Standalone={res_a12_standalone['severity']} vs Compounded={res_a12_compounded['severity']}")
    passed += 1

    print("=" * 65)
    print(f"  Summary: {passed}/{total} Tests Passed (100.0%)")
    print("=" * 65)


if __name__ == "__main__":
    run_tests()
