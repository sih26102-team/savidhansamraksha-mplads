"""
Savidhan Samraksha Multi-Model AI Detection System — Fusion & Decision Support Layer
Author: Kousic (ML Engine Lead) & Savidhan Samraksha Engineering Team

Architecture per Master Reference Specification:
Combines Module A (Financial & Temporal), Module B (Visual & Spatial), and
Module C (Satellite Earth Observation) into one calibrated risk score with:
  1. Graceful degradation: Inconclusive/absent modules dynamically re-normalize weights.
  2. Materiality weighting: Multiplies score by an absolute rupee value factor.
  3. Corroboration rule: Module A stall/billing inflation + Module B duplicate photo -> Escalates to CRITICAL (RED).
  4. Edge Case C (Cartel Scenario & Hierarchical Override): No-tender + repeated agency/approver overlap
     -> Overrides to HIGH RISK (RED) regardless of clean physical scores from Modules B & C.
  5. Edge Case D (Out-of-Distribution Novel Fraud): Unsupervised Isolation Forest outlier
     surfaces new fraud patterns for priority human review.
  6. Alert Categorization: Red (Critical/High), Yellow (Moderate), Green (Low) with plain-English rationales.
"""

import math
from typing import Any, Dict, List, Optional, Tuple, Set


class FusionEngine:
    """
    Master Decision Support & Cross-Module Fusion Layer.
    Executes weighted fusion, materiality calibration, corroboration,
    cartel collusion overrides, and alert generation.
    """

    def __init__(self, base_weights: Optional[Dict[str, float]] = None):
        # Default nominal weights across the three pillars
        self.base_weights = base_weights or {
            "module_a": 0.50,  # Financial & Temporal
            "module_b": 0.25,  # Visual & Spatial
            "module_c": 0.25,  # Satellite Remote Sensing
        }

    # --------------------------------------------------------------------------
    # 1. Materiality Weighting Factor
    # --------------------------------------------------------------------------
    def calculate_materiality_factor(self, rupee_amount: float) -> float:
        """
        Calculates materiality multiplier based on absolute rupee value.
        Higher financial outlays carry greater systemic fiduciary risk.

        Tiers:
          <= 5 Lakhs:        0.90 (Micro civic repair, minor noise de-escalation)
          > 5L to 25L:       1.00 (Standard baseline median)
          > 25L to 1 Crore:   1.08 (Substantial community work)
          > 1 Cr to 5 Crore:  1.15 (Major capital expenditure)
          > 5 Crore:          1.25 (Mega outlay, maximum fiduciary scrutiny)
        """
        v = float(rupee_amount or 0.0)
        if v <= 500_000.0:
            return 0.90
        elif v <= 2_500_000.0:
            return 1.00
        elif v <= 10_000_000.0:
            return 1.08
        elif v <= 50_000_000.0:
            return 1.15
        else:
            return 1.25

    # --------------------------------------------------------------------------
    # 2. Corroboration Detection (Module A Billing/Stall + Module B Reused Photo)
    # --------------------------------------------------------------------------
    def evaluate_corroboration(
        self,
        module_a_findings: List[Dict[str, Any]],
        module_b_findings: List[Dict[str, Any]],
        features: Optional[Dict[str, float]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Corroboration rule:
        When Module A's stall/inflated-billing detector and Module B's same-project
        duplicate-photo flag trigger together on the same work, escalate straight to Critical.
        """
        # Module A financial stall / billing indicators
        mod_a_stall_or_inflation = False
        a_detectors = {f.get("detector", "") for f in (module_a_findings or [])}
        a_titles = " ".join(f.get("title", "") for f in (module_a_findings or []))
        
        if (
            "COST_PER_UNIT_OUTLIER" in a_detectors
            or "PROGRESS_SILENCE_DORMANT" in a_detectors
            or "Disproportionate" in a_titles
            or "Divergence" in a_titles
            or (features and features.get("progressExpenditureDivergence", 0.0) > 0.15)
        ):
            mod_a_stall_or_inflation = True

        # Module B duplicate photo within same project
        mod_b_duplicate = False
        b_modules = {f.get("module", "") for f in (module_b_findings or [])}
        b_titles = " ".join(f.get("title", "") for f in (module_b_findings or []))
        
        if (
            "DUPLICATE_SEQUENTIAL_PHOTO" in b_modules
            or "DUPLICATE_CROSS_PROJECT_PHOTO" in b_modules
            or "Duplicate" in b_titles
            or "DUPLICATE" in b_titles.upper()
        ):
            mod_b_duplicate = True

        if mod_a_stall_or_inflation and mod_b_duplicate:
            finding = {
                "severity": "CRITICAL",
                "title": "Critical Corroborated Fraud Signal: Billing Divergence with Reused Ground Photos",
                "explanation": (
                    "Module A's financial stall / billing inflation anomaly is directly corroborated "
                    "by Module B's detection of duplicate milestone photographs. "
                    "Reported physical progress is synthetic while funds are flowing."
                ),
                "evidence": (
                    "Cross-module confirmation: Financial divergence coincided with identical perceptual photo hashes. "
                    "Immediate project freeze and physical site verification required."
                ),
                "module": "FUSION_CORROBORATION",
                "penalty": 40.0,
                "telemetry": {"corroborated": True, "escalateToCritical": True}
            }
            return True, finding

        return False, None

    # --------------------------------------------------------------------------
    # 3. Edge Case C: Cartel Scenario & Hierarchical Collusion Override
    # --------------------------------------------------------------------------
    def evaluate_cartel_collusion_override(
        self,
        project: Dict[str, Any],
        module_a_findings: List[Dict[str, Any]],
        project_history: Optional[List[Dict[str, Any]]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Edge Case C: The Cartel Scenario & Hierarchical Override.
        A corrupt cartel can physically construct a valid asset — yielding clean scores
        from Module B and Module C — while the procurement process was rigged.
        Hierarchical override:
          IF no-tender flag co-occurs with repeated agency/approver overlap,
          override marks project HIGH RISK regardless of clean physical scores.
        """
        tender_invited = project.get("tender_invited")
        if tender_invited is None:
            tender_invited = project.get("tenderInvited", True)

        has_no_tender = not tender_invited or any(
            f.get("detector") == "NO_TENDER_SANCTION" or "Tendering Omitted" in f.get("title", "")
            for f in (module_a_findings or [])
        )

        if not has_no_tender:
            return False, None

        agency_id = str(project.get("agency_id") or project.get("agencyId") or "").strip()
        approver_id = str(
            project.get("approver_id") or project.get("approverId") or
            project.get("collector_id") or project.get("mp_id") or ""
        ).strip()

        # Check repeated concentration across project history
        concentration_count = 1
        if project_history and agency_id and approver_id:
            for hp in project_history:
                h_agency = str(hp.get("agency_id") or hp.get("agencyId") or "").strip()
                h_approver = str(
                    hp.get("approver_id") or hp.get("approverId") or
                    hp.get("collector_id") or hp.get("mp_id") or ""
                ).strip()
                if h_agency == agency_id and h_approver == approver_id:
                    concentration_count += 1
        elif project.get("repeatedAgencyApproverOverlap") or project.get("cartel_suspected"):
            concentration_count = 3  # Explicit test / seeder flag

        # Cartel threshold: No tender + agency/approver overlap >= 2
        if concentration_count >= 2:
            override_finding = {
                "severity": "HIGH",
                "title": "Hierarchical Override: Financial Network Collusion & Bid-Rigging Suspected",
                "explanation": (
                    "Asset physically verified on ground and satellite, but high risk of "
                    "financial network collusion detected."
                ),
                "evidence": (
                    f"Hierarchical override applied: Statutory tendering was omitted (tender_invited=False) "
                    f"and repeated agency-approver concentration detected across peer projects "
                    f"(Agency: '{agency_id}', Approver: '{approver_id}', Recurrent pairings: {concentration_count}). "
                    f"Physical inspection clean, but single-source procurement captured."
                ),
                "module": "FUSION_COLLUSION_OVERRIDE",
                "penalty": 30.0,
                "telemetry": {
                    "hierarchicalOverride": True,
                    "agencyId": agency_id,
                    "approverId": approver_id,
                    "overlapCount": concentration_count
                }
            }
            return True, override_finding

        return False, None

    # --------------------------------------------------------------------------
    # 4. Edge Case D: Out-of-Distribution Novel Fraud via Isolation Forest
    # --------------------------------------------------------------------------
    def evaluate_novel_outlier(
        self,
        isolation_forest_score: float,
        isolation_forest_status: str,
        heuristics_fired: bool = False,
        feature_explanations: Optional[List[str]] = None
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """
        Edge Case D: Out-of-Distribution Novel Fraud.
        Fraud patterns not anticipated by rule-based detectors can slip past supervised checks.
        Isolation Forest is unsupervised — it surfaces statistically anomalous behavior without
        predefined rules, prioritizing novel patterns for human investigative review.
        """
        if isolation_forest_score > 75.0 or isolation_forest_status == "OUTLIER":
            numbered = ""
            if feature_explanations:
                numbered = " " + " ".join(f"[{i+1}] {exp}" for i, exp in enumerate(feature_explanations))

            note = (
                "Heuristic rules also fired on this project."
                if heuristics_fired
                else "No individual domain rule was breached alone — anomaly is driven by multi-dimensional statistical divergence."
            )

            finding = {
                "severity": "HIGH",
                "title": "Unusual Project Execution Pattern Flagged for Audit",
                "explanation": (
                    "Statistical audit detected an unusual combination of rapid payments, "
                    "extended dormancy, or milestone delays compared to peer projects in this region. "
                    "Surfaced for priority administrative review."
                ),
                "evidence": (
                    f"Unsupervised anomaly score: {round(isolation_forest_score, 1)}/100. "
                    f"{note}{numbered}"
                ),
                "module": "UNEXPLAINED_OUTLIER_ANOMALY",
                "penalty": 18.0,
                "telemetry": {
                    "novelOutlier": True,
                    "ifScore": round(isolation_forest_score, 1)
                }
            }
            return True, finding

        return False, None

    # --------------------------------------------------------------------------
    # 5. Master Fused Evaluation Method
    # --------------------------------------------------------------------------
    def fuse_modules(
        self,
        module_a_score: float,
        module_a_findings: List[Dict[str, Any]],
        module_b_score: Optional[float] = None,
        module_b_status: str = "AVAILABLE",
        module_b_findings: Optional[List[Dict[str, Any]]] = None,
        module_c_score: Optional[float] = None,
        module_c_status: str = "AVAILABLE",
        module_c_findings: Optional[List[Dict[str, Any]]] = None,
        isolation_forest_score: float = 0.0,
        isolation_forest_status: str = "INLIER",
        sanctioned_amount: float = 1.0,
        expenditure_incurred: float = 0.0,
        project: Optional[Dict[str, Any]] = None,
        project_history: Optional[List[Dict[str, Any]]] = None,
        features: Optional[Dict[str, float]] = None,
        feature_explanations: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Executes full Fusion & Decision Support pipeline:
          1. Weighted fusion across conclusive modules with graceful degradation.
          2. Materiality multiplier based on absolute rupee amount.
          3. Corroboration rule check (stall + duplicate photo -> Critical).
          4. Edge Case C: Hierarchical Cartel Collusion Override.
          5. Edge Case D: Unsupervised Novel Outlier surfacing.
          6. Alert level categorization (Red, Yellow, Green).
        """
        project = project or {}
        b_findings = module_b_findings or []
        c_findings = module_c_findings or []
        all_findings: List[Dict[str, Any]] = []

        # 1. Graceful Degradation & Dynamic Weight Re-normalization
        w_a = self.base_weights.get("module_a", 0.50)
        w_b = self.base_weights.get("module_b", 0.25)
        w_c = self.base_weights.get("module_c", 0.25)

        active_modules = ["A"]
        degraded_modules = []

        b_conclusive = (
            module_b_score is not None
            and module_b_status not in ("INCONCLUSIVE", "MISSING_EVIDENCE", "UNAVAILABLE")
        )
        if b_conclusive:
            active_modules.append("B")
        else:
            degraded_modules.append("B")

        c_conclusive = (
            module_c_score is not None
            and module_c_status not in ("INCONCLUSIVE", "SATELLITE_DATA_UNAVAILABLE_CLOUDY", "UNAVAILABLE")
        )
        if c_conclusive:
            active_modules.append("C")
        else:
            degraded_modules.append("C")

        # Sum active weights
        total_active_w = w_a
        if b_conclusive:
            total_active_w += w_b
        if c_conclusive:
            total_active_w += w_c

        # Compute base weighted fusion
        base_fused = (module_a_score * (w_a / total_active_w))
        if b_conclusive and module_b_score is not None:
            base_fused += (float(module_b_score) * (w_b / total_active_w))
        if c_conclusive and module_c_score is not None:
            base_fused += (float(module_c_score) * (w_c / total_active_w))

        base_fused = round(base_fused, 2)

        # 2. Materiality Weighting Factor
        rupee_val = max(float(sanctioned_amount or 0.0), float(expenditure_incurred or 0.0))
        materiality_factor = self.calculate_materiality_factor(rupee_val)
        material_adjusted_score = round(min(100.0, base_fused * materiality_factor), 2)

        raw_score = material_adjusted_score

        # 3. Corroboration Rule (Billing Inflation/Stall + Duplicate Photo -> CRITICAL)
        is_corroborated, corrob_finding = self.evaluate_corroboration(
            module_a_findings, b_findings, features
        )
        if is_corroborated and corrob_finding:
            raw_score = max(86.50, raw_score)
            all_findings.append(corrob_finding)

        # 4. Edge Case C: Cartel Scenario & Hierarchical Override
        is_cartel_override, cartel_finding = self.evaluate_cartel_collusion_override(
            project, module_a_findings, project_history
        )
        if is_cartel_override and cartel_finding:
            raw_score = max(75.80, raw_score)
            all_findings.append(cartel_finding)

        # 5. Edge Case D: Out-of-Distribution Novel Fraud
        heuristics_fired = any(f.get("severity") in ("HIGH", "MODERATE") for f in module_a_findings)
        is_novel, novel_finding = self.evaluate_novel_outlier(
            isolation_forest_score, isolation_forest_status, heuristics_fired, feature_explanations
        )
        if is_novel and novel_finding:
            all_findings.append(novel_finding)

        # Compound Ghost-Work floor: When IF marks OUTLIER (> 75) AND Module A is elevated (>= 50.0),
        # ensure the project is classified HIGH / RED (floor at 70.0)
        if isolation_forest_score > 75.0 and module_a_score >= 50.0:
            raw_score = max(raw_score, 70.0)

        # Workflow status / Data completeness statutory floors
        completeness = str(project.get("dataCompleteness") or "COMPLETE").upper()
        if completeness == "INCOMPLETE":
            raw_score = max(raw_score, 72.40 + (isolation_forest_score * 0.145))
        elif completeness == "PARTIAL":
            raw_score = max(raw_score, 38.60 + (isolation_forest_score * 0.112))

        wf_status = str(project.get("workflowStatus") or "NORMAL").upper()
        if wf_status in ("ESCALATED", "ESCALATED_STATE"):
            raw_score = max(raw_score, 75.80 + (isolation_forest_score * 0.184))

        final_score = round(max(6.40, min(98.60, raw_score)), 2)

        # 6. Categorized Alert (Red, Yellow, Green)
        if completeness == "INCOMPLETE":
            alert_category = "RED"
            risk_level = "DATA_INCOMPLETE"
        elif final_score >= 85.0 or is_corroborated:
            alert_category = "RED"
            risk_level = "CRITICAL"
        elif final_score >= 70.0 or is_cartel_override:
            alert_category = "RED"
            risk_level = "HIGH"
        elif final_score >= 40.0:
            alert_category = "YELLOW"
            risk_level = "MODERATE"
        else:
            alert_category = "GREEN"
            risk_level = "LOW"

        # Actionable plain-language summary for decision support
        if is_corroborated:
            actionable_summary = "CRITICAL ALERT: Physical progress claims are synthetic; financial divergence corroborated by duplicate ground photography."
        elif is_cartel_override:
            actionable_summary = "HIGH ALERT: Asset physically verified, but high risk of financial network collusion detected (No-tender + repeated agency concentration)."
        elif is_novel:
            actionable_summary = "HIGH ALERT: Novel out-of-distribution anomaly detected by unsupervised ML model; prioritized for human audit."
        elif alert_category == "RED":
            actionable_summary = "RED ALERT: High multi-module risk detected across financial, temporal, or ground observations."
        elif alert_category == "YELLOW":
            actionable_summary = "YELLOW ALERT: Moderate operational variance observed; milestone inspection advised."
        else:
            actionable_summary = "GREEN: Verified operational parameters; project conforms to standard milestones."

        return {
            "fusedScore": final_score,
            "riskScore": final_score,
            "riskLevel": risk_level,
            "alertCategory": alert_category,
            "actionableSummary": actionable_summary,
            "fusionFindings": all_findings,
            "telemetry": {
                "baseFusedScore": base_fused,
                "materialityFactor": materiality_factor,
                "rupeeValue": rupee_val,
                "activeModules": active_modules,
                "degradedModules": degraded_modules,
                "corroborationTriggered": is_corroborated,
                "hierarchicalOverrideActive": is_cartel_override,
                "novelOutlierDetected": is_novel,
            }
        }
