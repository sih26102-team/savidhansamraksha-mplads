"""
Model Performance & Accuracy Evaluation — Phase 1 (Isolation Forest)
Author: Kousic (ML Engine Lead)

Updated benchmark suite:
- Test 1: Normal on-track project → LOW, score < 35
- Test 2: Severe payment divergence (Ghost Work) → HIGH, score >= 65
- Test 3: Data Incomplete / Unaudited → DATA_INCOMPLETE, score >= 70
- Test 4: Unexplained Outlier — extreme scale outlier that heuristics can't
          explain alone → IF fires UNEXPLAINED_OUTLIER_ANOMALY module
- Test 5: Cold-start guard — only 5 peer samples → neutral IF contribution,
          heuristic rules still work correctly
"""

import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent))
from risk_engine import (
    evaluate_project_risk,
    IsolationForestAnomalyDetector,
    extract_isolation_features,
)


def run_benchmark():
    test_suite = [
        # ------------------------------------------------------------------
        # Test 1: Healthy, on-track project
        # ------------------------------------------------------------------
        {
            "name": "Normal On-Track Project",
            "data": {
                "workId": "BENCH-001",
                "estimatedCost": 2_500_000,
                "sanctionedAmount": 2_500_000,
                "expenditureIncurred": 1_200_000,
                "physicalProgressPct": 52.0,
                "dateOfSanction": "2026-01-01T00:00:00Z",
                "expectedCompletionDate": "2026-12-31T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE",
            },
            "expected_level": "LOW",
            "max_score": 35.0,
        },
        # ------------------------------------------------------------------
        # Test 2: Severe payment divergence — classic ghost-work pattern
        #   92% of sanctioned funds disbursed, only 18% physical progress
        #   Both heuristics AND isolation forest should fire HIGH
        # ------------------------------------------------------------------
        {
            "name": "Severe Payment Divergence Anomaly (Ghost Work Risk)",
            "data": {
                "workId": "BENCH-002",
                "estimatedCost": 10_000_000,
                "sanctionedAmount": 10_000_000,
                "expenditureIncurred": 9_200_000,
                "physicalProgressPct": 18.0,
                "dateOfSanction": "2023-01-01T00:00:00Z",
                "expectedCompletionDate": "2024-01-01T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE",
            },
            "expected_level": "HIGH",
            "min_score": 65.0,          # 70/30 hybrid lowers absolute ceiling vs pure heuristic
        },
        # ------------------------------------------------------------------
        # Test 3: Incomplete data — forced floor at 72.4+
        # ------------------------------------------------------------------
        {
            "name": "Data Incomplete / Unaudited Project",
            "data": {
                "workId": "BENCH-003",
                "estimatedCost": 4_000_000,
                "sanctionedAmount": 4_000_000,
                "expenditureIncurred": 2_000_000,
                "physicalProgressPct": 50.0,
                "dateOfSanction": "2024-01-01T00:00:00Z",
                "expectedCompletionDate": "2024-08-01T00:00:00Z",
                "tenderInvited": False,
                "ucFiled": False,
                "dataCompleteness": "INCOMPLETE",
            },
            "expected_level": "DATA_INCOMPLETE",
            "min_score": 70.0,
        },
        # ------------------------------------------------------------------
        # Test 4: Extreme-scale outlier — ₹8.5 Cr project with only 22%
        #         physical progress but no single heuristic exceeds threshold.
        #         Isolation Forest should surface UNEXPLAINED_OUTLIER_ANOMALY.
        # ------------------------------------------------------------------
        {
            "name": "Subtle Multi-Dimensional Statistical Outlier",
            "data": {
                "workId": "BENCH-004",
                "estimatedCost": 85_000_000,
                "sanctionedAmount": 85_000_000,
                "expenditureIncurred": 45_000_000,
                "physicalProgressPct": 40.0,
                "dateOfSanction": "2024-01-01T00:00:00Z",
                "expectedCompletionDate": "2025-01-01T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE",
            },
            "expect_outlier_flag": True,   # UNEXPLAINED_OUTLIER_ANOMALY module
        },
        # ------------------------------------------------------------------
        # Test 5: Cold-start guard — only 5 peer samples
        #         IF should return 0.0 / INSUFFICIENT_PEER_DATA;
        #         heuristics still evaluate correctly
        # ------------------------------------------------------------------
        {
            "name": "Cold-Start Guard (< 10 Peer Samples)",
            "cold_start_n": 5,
            "data": {
                "workId": "BENCH-005",
                "estimatedCost": 3_000_000,
                "sanctionedAmount": 3_000_000,
                "expenditureIncurred": 2_700_000,
                "physicalProgressPct": 20.0,
                "dateOfSanction": "2023-06-01T00:00:00Z",
                "expectedCompletionDate": "2024-06-01T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE",
            },
            "expect_if_status": "INSUFFICIENT_PEER_DATA",
            "expect_if_score": 0.0,
        },
    ]

    print("=" * 58)
    print("   CIVICSHIELD ML ENGINE BENCHMARK SUITE — PHASE 1")
    print("=" * 58)
    passed = 0
    total = len(test_suite)

    for idx, test in enumerate(test_suite, 1):
        data = test["data"]
        cold_n = test.get("cold_start_n")

        if cold_n is not None:
            # Build a temporary cold-start detector
            tiny_corpus = [data] * cold_n
            cold_det = IsolationForestAnomalyDetector()
            cold_det.fit(tiny_corpus)
            if_score, if_status = cold_det.score_project(data)
            # Still run full evaluate for heuristic output
            res = evaluate_project_risk(data)
            res["isolationForestScore"] = if_score
            res["isolationForestStatus"] = if_status
        else:
            res = evaluate_project_risk(data)

        score  = res["riskScore"]
        level  = res["riskLevel"]
        if_sc  = res.get("isolationForestScore", 0.0)
        if_st  = res.get("isolationForestStatus", "")
        peer_n = res.get("peerSampleCount", 0)
        findings_modules = [f["module"] for f in res.get("findings", [])]

        ok = True
        fail_reasons: List[str] = []

        if "max_score" in test and score > test["max_score"]:
            ok = False
            fail_reasons.append(
                f"score {score} > max {test['max_score']}"
            )
        if "min_score" in test and score < test["min_score"]:
            ok = False
            fail_reasons.append(
                f"score {score} < min {test['min_score']}"
            )
        if "expected_level" in test and test["expected_level"] != level:
            ok = False
            fail_reasons.append(
                f"level '{level}' != expected '{test['expected_level']}'"
            )
        if test.get("expect_outlier_flag"):
            if "UNEXPLAINED_OUTLIER_ANOMALY" not in findings_modules:
                ok = False
                fail_reasons.append("UNEXPLAINED_OUTLIER_ANOMALY flag not raised")
        if "expect_if_status" in test and if_st != test["expect_if_status"]:
            ok = False
            fail_reasons.append(
                f"IF status '{if_st}' != expected '{test['expect_if_status']}'"
            )
        if "expect_if_score" in test and if_sc != test["expect_if_score"]:
            ok = False
            fail_reasons.append(
                f"IF score {if_sc} != expected {test['expect_if_score']}"
            )

        status_tag = "PASSED" if ok else "FAILED"
        if ok:
            passed += 1

        print(f"\n[{status_tag}] Test {idx}: {test['name']}")
        print(
            f"         riskScore={score} | level={level} | "
            f"IF={if_sc} ({if_st}) | peers={peer_n}"
        )
        print(
            f"         findings=[{', '.join(findings_modules)}]"
        )
        if fail_reasons:
            for r in fail_reasons:
                print(f"         FAIL: {r}")

    print("\n" + "-" * 58)
    print(
        f"Summary: {passed}/{total} Tests Passed "
        f"({(passed/total)*100:.1f}%)"
    )
    print("=" * 58)
    return passed == total


if __name__ == "__main__":
    success = run_benchmark()
    sys.exit(0 if success else 1)
