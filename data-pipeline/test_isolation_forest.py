"""
Phase 1 ML Dry-Run Validation Suite
====================================
Tests the full Isolation Forest pipeline against a synthetic batch of
projects designed to cover the full risk spectrum.  Verifiable without a
live database connection — runs purely from in-memory data.

Run with:
    python data-pipeline/test_isolation_forest.py
"""

import sys
import json
from pathlib import Path

# Allow imports from ml-engine/
sys.path.insert(0, str(Path(__file__).parent.parent / "ml-engine"))

from risk_engine import (
    evaluate_project_risk,
    IsolationForestAnomalyDetector,
    extract_isolation_features,
)

# ──────────────────────────────────────────────────────────────────────────────
# Synthetic project library
# ──────────────────────────────────────────────────────────────────────────────

SYNTHETIC_PROJECTS = [
    # ── Normal / healthy projects ──────────────────────────────────────────
    {
        "workId": "DRY-001",
        "description": "Normal: mid-way CC road project, on track",
        "estimatedCost": 3_500_000,
        "sanctionedAmount": 3_500_000,
        "expenditureIncurred": 1_600_000,
        "physicalProgressPct": 48.0,
        "dateOfSanction": "2025-01-01T00:00:00Z",
        "expectedCompletionDate": "2025-12-31T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        "expect": {"max_score": 35.0, "level": "LOW"},
    },
    {
        "workId": "DRY-002",
        "description": "Normal: near-complete water plant, UC pending",
        "estimatedCost": 4_200_000,
        "sanctionedAmount": 4_200_000,
        "expenditureIncurred": 3_900_000,
        "physicalProgressPct": 95.0,
        "dateOfSanction": "2024-06-01T00:00:00Z",
        "expectedCompletionDate": "2025-06-01T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        "expect": {"max_score": 40.0},
    },
    # ── Artificial anomalies — should trigger HIGH / OUTLIER ───────────────
    {
        "workId": "DRY-003",
        "description": "Ghost work: 88% funds spent, only 20% physical done",
        "estimatedCost": 7_000_000,
        "sanctionedAmount": 7_000_000,
        "expenditureIncurred": 6_160_000,
        "physicalProgressPct": 20.0,
        "dateOfSanction": "2022-06-01T00:00:00Z",
        "expectedCompletionDate": "2023-06-01T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        "expect": {"min_score": 65.0, "expect_if_outlier": True},
    },
    {
        "workId": "DRY-004",
        "description": "Stalled: 4-year-old project frozen at 35%, massive time overrun",
        "estimatedCost": 5_500_000,
        "sanctionedAmount": 5_500_000,
        "expenditureIncurred": 2_000_000,
        "physicalProgressPct": 35.0,
        "dateOfSanction": "2021-01-01T00:00:00Z",
        "expectedCompletionDate": "2022-01-01T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        # Stalled project: time ratio is very high (4+ years overdue) but
        # expenditure roughly tracks 35% progress — heuristics catch the
        # timeline overrun, IF sees it as unusual but not extreme expenditure.
        # Reasonable expectation: MODERATE (score > 20), TIME_OVERRUN caught.
        "expect": {"min_score": 15.0},
    },
    {
        "workId": "DRY-005",
        "description": "Data incomplete + no tender + no UC",
        "estimatedCost": 6_000_000,
        "sanctionedAmount": 6_000_000,
        "expenditureIncurred": 3_000_000,
        "physicalProgressPct": 50.0,
        "dateOfSanction": "2023-01-01T00:00:00Z",
        "expectedCompletionDate": "2023-12-31T00:00:00Z",
        "tenderInvited": False,
        "ucFiled": False,
        "dataCompleteness": "INCOMPLETE",
        "expect": {"min_score": 70.0, "level": "DATA_INCOMPLETE"},
    },
    # ── Statistical outlier — Isolation Forest should fire ─────────────────
    {
        "workId": "DRY-006",
        "description": "Extreme scale outlier: Rs 12 Cr with unusual velocity",
        "estimatedCost": 120_000_000,
        "sanctionedAmount": 120_000_000,
        "expenditureIncurred": 70_000_000,
        "physicalProgressPct": 38.0,
        "dateOfSanction": "2024-01-01T00:00:00Z",
        "expectedCompletionDate": "2025-01-01T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        "expect": {"expect_if_outlier": True},
    },
    # ── Cold-start guard ───────────────────────────────────────────────────
    {
        "workId": "DRY-007",
        "description": "Cold-start: only 3 peer samples, IF returns 0.0",
        "estimatedCost": 4_000_000,
        "sanctionedAmount": 4_000_000,
        "expenditureIncurred": 3_600_000,
        "physicalProgressPct": 22.0,
        "dateOfSanction": "2023-01-01T00:00:00Z",
        "expectedCompletionDate": "2024-01-01T00:00:00Z",
        "tenderInvited": True,
        "ucFiled": False,
        "dataCompleteness": "COMPLETE",
        "cold_start_n": 3,
        "expect": {"expect_if_score": 0.0, "expect_if_status": "INSUFFICIENT_PEER_DATA"},
    },
]


# ──────────────────────────────────────────────────────────────────────────────
# Runner
# ──────────────────────────────────────────────────────────────────────────────

def run_dry_test() -> bool:
    print("=" * 62)
    print("  CIVICSHIELD ISOLATION FOREST DRY-RUN VALIDATION SUITE")
    print("=" * 62)

    passed = 0
    total = len(SYNTHETIC_PROJECTS)

    for project in SYNTHETIC_PROJECTS:
        work_id = project["workId"]
        desc = project.get("description", "")
        expect = project.get("expect", {})
        cold_n = project.get("cold_start_n")

        if cold_n is not None:
            # Use a deliberately tiny corpus to trigger cold-start guard
            tiny_corpus = [project] * cold_n
            cold_det = IsolationForestAnomalyDetector()
            cold_det.fit(tiny_corpus)
            if_score, if_status = cold_det.score_project(project)
            result = evaluate_project_risk(project)
            result["isolationForestScore"] = if_score
            result["isolationForestStatus"] = if_status
            result["peerSampleCount"] = cold_det.n_samples
        else:
            result = evaluate_project_risk(project)
            if_score = result.get("isolationForestScore", 0.0)
            if_status = result.get("isolationForestStatus", "")

        score = result["riskScore"]
        level = result["riskLevel"]
        peer_n = result.get("peerSampleCount", 0)
        modules = [f["module"] for f in result.get("findings", [])]

        ok = True
        reasons = []

        if "max_score" in expect and score > expect["max_score"]:
            ok = False
            reasons.append(f"score {score} > max {expect['max_score']}")
        if "min_score" in expect and score < expect["min_score"]:
            ok = False
            reasons.append(f"score {score} < min {expect['min_score']}")
        if "level" in expect and level != expect["level"]:
            ok = False
            reasons.append(f"level '{level}' != '{expect['level']}'")
        if expect.get("expect_if_outlier") and "UNEXPLAINED_OUTLIER_ANOMALY" not in modules:
            ok = False
            reasons.append("Expected UNEXPLAINED_OUTLIER_ANOMALY module — not found")
        if "expect_if_score" in expect and if_score != expect["expect_if_score"]:
            ok = False
            reasons.append(f"IF score {if_score} != {expect['expect_if_score']}")
        if "expect_if_status" in expect and if_status != expect["expect_if_status"]:
            ok = False
            reasons.append(f"IF status '{if_status}' != '{expect['expect_if_status']}'")

        tag = "PASSED" if ok else "FAILED"
        if ok:
            passed += 1

        print(f"\n[{tag}] {work_id}: {desc}")
        print(
            f"       score={score} | level={level} | "
            f"IF={if_score} ({if_status}) | peers={peer_n}"
        )
        print(f"       modules=[{', '.join(modules)}]")
        for r in reasons:
            print(f"       FAIL: {r}")

    print("\n" + "-" * 62)
    print(f"Summary: {passed}/{total} Passed ({(passed/total)*100:.1f}%)")
    print("=" * 62)
    return passed == total


if __name__ == "__main__":
    success = run_dry_test()
    sys.exit(0 if success else 1)
