"""
Feature Engineering Pipeline for SavidhanSamraksha Infrastructure Auditing.
Author: Kousic (ML Engine Lead)
"""

from datetime import datetime
from typing import Dict, Any, List

def calculate_time_elapsed_ratio(date_of_sanction: str, expected_completion: str, actual_completion: str = None) -> float:
    try:
        sanction_dt = datetime.fromisoformat(date_of_sanction.replace("Z", "+00:00"))
        expected_dt = datetime.fromisoformat(expected_completion.replace("Z", "+00:00"))
        
        now = datetime.now(sanction_dt.tzinfo)
        end_ref = datetime.fromisoformat(actual_completion.replace("Z", "+00:00")) if actual_completion else now
        
        total_planned = (expected_dt - sanction_dt).total_seconds()
        if total_planned <= 0:
            return 1.2
            
        elapsed = (end_ref - sanction_dt).total_seconds()
        return round(max(0.0, min(3.0, elapsed / total_planned)), 3)
    except Exception:
        return 0.85

def extract_feature_vector(project: Dict[str, Any]) -> Dict[str, float]:
    """
    Transforms raw project dictionary into normalized numeric features (0.0 to 1.0+).
    """
    estimated_cost = float(project.get("estimatedCost") or 1.0)
    sanctioned_amount = float(project.get("sanctionedAmount") or estimated_cost)
    expenditure = float(project.get("expenditureIncurred") or 0.0)
    physical_progress = float(project.get("physicalProgressPct") or 0.0)
    
    cost_ratio = round(sanctioned_amount / max(1.0, estimated_cost), 4)
    expenditure_rate = round(expenditure / max(1.0, sanctioned_amount), 4)
    progress_rate = round(physical_progress / 100.0, 4)
    divergence = round(expenditure_rate - progress_rate, 4)
    
    sanction_date = str(project.get("dateOfSanction") or "2024-01-01T00:00:00Z")
    expected_date = str(project.get("expectedCompletionDate") or "2025-01-01T00:00:00Z")
    actual_date = project.get("actualCompletionDate")
    time_ratio = calculate_time_elapsed_ratio(sanction_date, expected_date, actual_date)
    
    # Governance compliance
    tender_ok = bool(project.get("tenderInvited", True))
    uc_ok = bool(project.get("ucFiled", False)) if (physical_progress >= 100 or expenditure_rate >= 0.9) else True
    completeness = project.get("dataCompleteness", "COMPLETE")
    
    gov_score = 1.0
    if not tender_ok:
        gov_score -= 0.4
    if not uc_ok:
        gov_score -= 0.3
    if completeness == "INCOMPLETE":
        gov_score -= 0.3
    elif completeness == "PARTIAL":
        gov_score -= 0.15
    gov_score = max(0.0, min(1.0, round(gov_score, 3)))
    
    # Evidence integrity
    missing_photos = int(project.get("photoMetadataMissingCount") or 0)
    dup_photos = int(project.get("photoDuplicateCount") or 0)
    evidence_score = 1.0 - (missing_photos * 0.12) - (dup_photos * 0.25)
    evidence_score = max(0.0, min(1.0, round(evidence_score, 3)))
    
    return {
        "costRatio": cost_ratio,
        "expenditureRate": expenditure_rate,
        "progressRate": progress_rate,
        "progressExpenditureDivergence": divergence,
        "timeElapsedRatio": time_ratio,
        "governanceComplianceScore": gov_score,
        "evidenceIntegrityScore": evidence_score
    }
