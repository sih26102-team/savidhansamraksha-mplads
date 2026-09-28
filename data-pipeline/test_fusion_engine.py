"""
Savidhan Samraksha Validation Suite — Fusion & Decision Support Layer
Author: Kousic & Phaneendra

Validates the complete Fusion Layer per the Master Reference Specification:
  TEST-F01: Standard 3-module clean fusion (Green / Low Risk)
  TEST-F02: Graceful degradation when Module B (Visual) is inconclusive
  TEST-F03: Graceful degradation when Module C (Satellite) has cloud occlusion
  TEST-F04: Materiality weighting factor (Mega outlay Rs 12 Cr vs Micro Rs 2 Lakh)
  TEST-F05: Corroboration Rule: Financial stall + duplicate photo -> Escalates to CRITICAL (RED)
  TEST-F06: Edge Case C (Cartel Scenario & Hierarchical Override): Clean physical B & C,
            but No-Tender + Repeated Agency/Approver concentration -> Overrides to HIGH RISK (RED)
  TEST-F07: Edge Case D (Out-of-Distribution Novel Fraud): Unsupervised Isolation Forest outlier
  TEST-F08: Full integration through evaluate_project_risk()
"""

import sys
from pathlib import Path

# Add ml-engine to sys.path
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-engine"))

from fusion_engine import FusionEngine

def run_tests():
    print("=" * 68)
    print("  SAVIDHAN SAMRAKSHA: FUSION & DECISION SUPPORT LAYER TESTS")
    print("=" * 68)

    fusion = FusionEngine()
    passed = 0
    total = 8

    # --------------------------------------------------------------------------
    # TEST-F01: Standard 3-module clean fusion (Green / Low Risk)
    # --------------------------------------------------------------------------
    res_f01 = fusion.fuse_modules(
        module_a_score=15.0,
        module_a_findings=[],
        module_b_score=10.0,
        module_b_status="AVAILABLE",
        module_b_findings=[],
        module_c_score=5.0,
        module_c_status="VERIFIED_ACTIVE_CONSTRUCTION",
        module_c_findings=[],
        sanctioned_amount=2_000_000,
    )
    assert res_f01["alertCategory"] == "GREEN", f"Expected GREEN alert, got {res_f01['alertCategory']}"
    assert res_f01["riskLevel"] == "LOW", f"Expected LOW risk level, got {res_f01['riskLevel']}"
    assert res_f01["telemetry"]["activeModules"] == ["A", "B", "C"], f"Expected all 3 active, got {res_f01['telemetry']['activeModules']}"
    print(f"[PASSED] TEST-F01: Standard 3-module clean fusion (Score={res_f01['fusedScore']}, Alert={res_f01['alertCategory']}, Level={res_f01['riskLevel']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F02: Graceful degradation when Module B (Visual) is inconclusive
    # --------------------------------------------------------------------------
    res_f02 = fusion.fuse_modules(
        module_a_score=30.0,
        module_a_findings=[],
        module_b_score=None,
        module_b_status="INCONCLUSIVE",
        module_c_score=10.0,
        module_c_status="VERIFIED_ACTIVE_CONSTRUCTION",
        sanctioned_amount=2_000_000,
    )
    # Active weights should be A (0.50) and C (0.25) -> Normalized: A = 0.667, C = 0.333
    expected_base = (30.0 * (0.50 / 0.75)) + (10.0 * (0.25 / 0.75))  # 20.0 + 3.33 = 23.33
    assert abs(res_f02["telemetry"]["baseFusedScore"] - expected_base) < 0.2, f"Expected {expected_base}, got {res_f02['telemetry']['baseFusedScore']}"
    assert "B" in res_f02["telemetry"]["degradedModules"], "Expected Module B in degradedModules"
    print(f"[PASSED] TEST-F02: Graceful degradation when Module B is inconclusive (Dynamic re-normalization base={res_f02['telemetry']['baseFusedScore']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F03: Graceful degradation when Module C (Satellite) has cloud cover
    # --------------------------------------------------------------------------
    res_f03 = fusion.fuse_modules(
        module_a_score=40.0,
        module_a_findings=[],
        module_b_score=20.0,
        module_b_status="AVAILABLE",
        module_c_score=None,
        module_c_status="SATELLITE_DATA_UNAVAILABLE_CLOUDY",
        sanctioned_amount=2_000_000,
    )
    # Active weights should be A (0.50) and B (0.25) -> Normalized: A = 0.667, B = 0.333
    expected_base_c = (40.0 * (0.50 / 0.75)) + (20.0 * (0.25 / 0.75))  # 26.67 + 6.67 = 33.33
    assert abs(res_f03["telemetry"]["baseFusedScore"] - expected_base_c) < 0.2, f"Expected {expected_base_c}, got {res_f03['telemetry']['baseFusedScore']}"
    assert "C" in res_f03["telemetry"]["degradedModules"], "Expected Module C in degradedModules"
    print(f"[PASSED] TEST-F03: Graceful degradation for cloudy satellite (Re-normalized base={res_f03['telemetry']['baseFusedScore']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F04: Materiality weighting factor (Mega outlay Rs 12 Cr vs Micro Rs 2 Lakh)
    # --------------------------------------------------------------------------
    m_micro = fusion.calculate_materiality_factor(200_000.0)      # Rs 2 Lakhs
    m_mega = fusion.calculate_materiality_factor(120_000_000.0)   # Rs 12 Crores
    assert m_micro == 0.90, f"Expected 0.90 for micro work, got {m_micro}"
    assert m_mega == 1.25, f"Expected 1.25 for mega work, got {m_mega}"

    res_micro = fusion.fuse_modules(module_a_score=50.0, module_a_findings=[], sanctioned_amount=200_000.0)
    res_mega = fusion.fuse_modules(module_a_score=50.0, module_a_findings=[], sanctioned_amount=120_000_000.0)
    assert res_mega["fusedScore"] > res_micro["fusedScore"], "Expected mega work to have higher materiality-weighted score"
    print(f"[PASSED] TEST-F04: Materiality weighting scaling (Micro Mf={m_micro} -> {res_micro['fusedScore']} vs Mega Mf={m_mega} -> {res_mega['fusedScore']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F05: Corroboration Rule: Financial stall + duplicate photo -> CRITICAL (RED)
    # --------------------------------------------------------------------------
    res_corrob = fusion.fuse_modules(
        module_a_score=45.0,
        module_a_findings=[
            {"detector": "PROGRESS_SILENCE_DORMANT", "severity": "HIGH", "title": "Prolonged Progress Silence"}
        ],
        module_b_score=35.0,
        module_b_findings=[
            {"module": "DUPLICATE_SEQUENTIAL_PHOTO", "severity": "HIGH", "title": "Sequential Duplicate Photo Detected"}
        ],
        sanctioned_amount=4_000_000,
    )
    assert res_corrob["telemetry"]["corroborationTriggered"] is True, "Expected corroboration to trigger"
    assert res_corrob["alertCategory"] == "RED", f"Expected RED alert, got {res_corrob['alertCategory']}"
    assert res_corrob["riskLevel"] == "CRITICAL", f"Expected CRITICAL risk level, got {res_corrob['riskLevel']}"
    assert res_corrob["fusedScore"] >= 86.5, f"Expected score >= 86.5, got {res_corrob['fusedScore']}"
    print(f"[PASSED] TEST-F05: Corroboration Rule verified (Score={res_corrob['fusedScore']}, RiskLevel={res_corrob['riskLevel']}, Alert={res_corrob['alertCategory']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F06: Edge Case C: Cartel Scenario & Hierarchical Override
    # Clean physical B & C, but No-Tender + Repeated Agency/Approver concentration
    # --------------------------------------------------------------------------
    cartel_project = {
        "workId": "WS-CARTEL-01",
        "tender_invited": False,
        "agency_id": "AGENCY-ALPHA",
        "approver_id": "APPROVER-BETA",
        "sanctioned_amount": 5_000_000
    }
    history = [
        {"agency_id": "AGENCY-ALPHA", "approver_id": "APPROVER-BETA"},
        {"agency_id": "AGENCY-ALPHA", "approver_id": "APPROVER-BETA"},
    ]
    res_cartel = fusion.fuse_modules(
        module_a_score=20.0,
        module_a_findings=[{"detector": "NO_TENDER_SANCTION", "title": "Statutory Competitive Tendering Omitted"}],
        module_b_score=5.0,   # Physical photos completely clean!
        module_b_status="AVAILABLE",
        module_c_score=5.0,   # Satellite ground transformation completely clean!
        module_c_status="VERIFIED_ACTIVE_CONSTRUCTION",
        project=cartel_project,
        project_history=history,
        sanctioned_amount=5_000_000,
    )
    assert res_cartel["telemetry"]["hierarchicalOverrideActive"] is True, "Expected cartel hierarchical override to activate"
    assert res_cartel["alertCategory"] == "RED", f"Expected RED alert, got {res_cartel['alertCategory']}"
    assert res_cartel["riskLevel"] == "HIGH", f"Expected HIGH risk level, got {res_cartel['riskLevel']}"
    assert res_cartel["fusedScore"] >= 75.0, f"Expected score >= 75.0, got {res_cartel['fusedScore']}"
    assert any("financial network collusion" in f.get("explanation", "").lower() for f in res_cartel["fusionFindings"]), "Expected collusion finding rationale"
    print(f"[PASSED] TEST-F06: Cartel Hierarchical Override verified (Score={res_cartel['fusedScore']}, Level={res_cartel['riskLevel']}, Alert={res_cartel['alertCategory']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F07: Edge Case D: Out-of-Distribution Novel Fraud via Isolation Forest
    # --------------------------------------------------------------------------
    res_novel = fusion.fuse_modules(
        module_a_score=25.0,
        module_a_findings=[],
        isolation_forest_score=82.5,
        isolation_forest_status="OUTLIER",
        sanctioned_amount=3_000_000,
        feature_explanations=["Payment velocity delta is 2.8 sigma above norm"]
    )
    assert res_novel["telemetry"]["novelOutlierDetected"] is True, "Expected novel outlier to be detected"
    assert any(f.get("module") == "UNEXPLAINED_OUTLIER_ANOMALY" for f in res_novel["fusionFindings"]), "Expected UNEXPLAINED_OUTLIER_ANOMALY finding"
    print(f"[PASSED] TEST-F07: Out-of-Distribution Novel Fraud surfaced (IF Anomaly Score=82.5/100, Alert={res_novel['alertCategory']})")
    passed += 1

    # --------------------------------------------------------------------------
    # TEST-F08: Full Integration through evaluate_project_risk()
    # --------------------------------------------------------------------------
    from risk_engine import evaluate_project_risk
    integrated_sample = {
        "workId": "TEST-FUSION-INT-01",
        "estimatedCost": 6_000_000,
        "sanctionedAmount": 6_500_000,
        "expenditureIncurred": 5_800_000,
        "physicalProgressPct": 25.0,
        "dateOfSanction": "2023-01-01T00:00:00Z",
        "expectedCompletionDate": "2024-01-01T00:00:00Z",
        "tenderInvited": False,
        "agency_id": "AGENCY-COLLUSION",
        "approver_id": "APPROVER-COLLUSION",
        "repeatedAgencyApproverOverlap": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
    }
    int_result = evaluate_project_risk(integrated_sample)
    assert "fusion" in int_result or "fusionSummary" in int_result or "alertCategory" in int_result, "Expected fusion payload in evaluate_project_risk"
    assert int_result["riskScore"] >= 70.0, f"Expected riskScore >= 70.0 for collusion project, got {int_result['riskScore']}"
    print(f"[PASSED] TEST-F08: Full integration through evaluate_project_risk() (Score={int_result['riskScore']}, Level={int_result['riskLevel']})")
    passed += 1

    print("=" * 68)
    print(f"  Summary: {passed}/{total} Tests Passed (100.0%)")
    print("=" * 68)


if __name__ == "__main__":
    run_tests()
