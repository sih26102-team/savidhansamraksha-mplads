"""
Model Performance & Accuracy Evaluation
Author: Kousic (ML Engine Lead)
"""

import math
from typing import List, Dict, Any
from risk_engine import evaluate_project_risk

def run_benchmark():
    test_suite = [
        {
            "name": "Normal On-Track Project",
            "data": {
                "workId": "BENCH-001",
                "estimatedCost": 2500000,
                "sanctionedAmount": 2500000,
                "expenditureIncurred": 1200000,
                "physicalProgressPct": 52.0,
                "dateOfSanction": "2026-01-01T00:00:00Z",
                "expectedCompletionDate": "2026-12-31T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE"
            },
            "expected_level": "LOW",
            "max_score": 35.0
        },
        {
            "name": "Severe Payment Divergence Anomaly (Ghost Work Risk)",
            "data": {
                "workId": "BENCH-002",
                "estimatedCost": 10000000,
                "sanctionedAmount": 10000000,
                "expenditureIncurred": 9200000,
                "physicalProgressPct": 18.0,
                "dateOfSanction": "2023-01-01T00:00:00Z",
                "expectedCompletionDate": "2024-01-01T00:00:00Z",
                "tenderInvited": True,
                "ucFiled": False,
                "dataCompleteness": "COMPLETE"
            },
            "expected_level": "HIGH",
            "min_score": 70.0
        },
        {
            "name": "Data Incomplete / Unaudited Project",
            "data": {
                "workId": "BENCH-003",
                "estimatedCost": 4000000,
                "sanctionedAmount": 4000000,
                "expenditureIncurred": 2000000,
                "physicalProgressPct": 50.0,
                "dateOfSanction": "2024-01-01T00:00:00Z",
                "expectedCompletionDate": "2024-08-01T00:00:00Z",
                "tenderInvited": False,
                "ucFiled": False,
                "dataCompleteness": "INCOMPLETE"
            },
            "expected_level": "DATA_INCOMPLETE",
            "min_score": 70.0
        }
    ]
    
    print("==================================================")
    print("   CIVICSHIELD ML ENGINE BENCHMARK SUITE          ")
    print("==================================================")
    passed = 0
    for idx, test in enumerate(test_suite, 1):
        res = evaluate_project_risk(test["data"])
        score = res["riskScore"]
        level = res["riskLevel"]
        
        ok = True
        if "max_score" in test and score > test["max_score"]:
            ok = False
        if "min_score" in test and score < test["min_score"]:
            ok = False
        if test["expected_level"] != level:
            ok = False
            
        status = "PASSED" if ok else "FAILED"
        if ok:
            passed += 1
        print(f"[{status}] Test {idx}: {test['name']}")
        print(f"         Score: {score} | Level: {level} | IsoConfidence: {res['anomalyConfidence']}")
        
    print("--------------------------------------------------")
    print(f"Summary: {passed}/{len(test_suite)} Tests Passed ({(passed/len(test_suite))*100:.1f}%)")
    print("==================================================")

if __name__ == "__main__":
    run_benchmark()
