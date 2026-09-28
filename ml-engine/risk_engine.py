"""
CivicShield Machine Learning Risk & Anomaly Inference Engine — Phase 1 (Isolation Forest)
Author: Kousic (ML Engine Lead)

Architecture:
- Layer 1 (Heuristic / Domain Rules Engine): 70% weight
  Explicit domain rules for cost overruns, temporal delays, expenditure-progress
  divergences, governance compliance, and photographic evidence integrity.

- Layer 2 (Isolation Forest Unsupervised Engine): 30% weight
  scikit-learn IsolationForest trained on a synthetic peer-baseline drawn from
  the same statistical distribution as real MPLADS projects.  Uses
  decision_function() mapped through a logistic transform to a 0–100 score.
  Cold-start guard: if < 10 peer samples are available the IF layer returns 0.0
  and marks the project INSUFFICIENT_PEER_DATA so the composite stays pure
  heuristic.

- UNEXPLAINED_OUTLIER_ANOMALY: appended when IF score > 75 but no heuristic rule
  fired, capturing invisible multi-dimensional abnormalities across the
  combined expenditure × timeline × velocity feature space.

Output keys (backward-compatible, no schema changes to any FastAPI route):
  workId, riskScore, riskLevel, anomalyConfidence, features, findings,
  moduleScores, isolationForestScore, isolationForestStatus, peerSampleCount
"""

import sys
import json
import math
import argparse
import numpy as np
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

# sklearn import — guarded so that a missing wheel doesn't crash the FastAPI
# boot; falls back to the analytic proxy used in the original engine.
try:
    from sklearn.ensemble import IsolationForest as _SKIsolationForest
    _SKLEARN_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SKLEARN_AVAILABLE = False

from feature_engineering import extract_feature_vector

# Satellite engine import (Phase 3) — guarded so engine boots cleanly anywhere
try:
    from satellite_engine import analyze_satellite_ground_change
    _SATELLITE_AVAILABLE = True
except ImportError:
    try:
        from ml_engine.satellite_engine import analyze_satellite_ground_change
        _SATELLITE_AVAILABLE = True
    except ImportError:
        analyze_satellite_ground_change = None
        _SATELLITE_AVAILABLE = False

# ---------------------------------------------------------------------------
# Weights & configuration
# ---------------------------------------------------------------------------

WEIGHTS_PATH = Path(__file__).parent / "model_artifacts" / "weights.json"


def load_weights() -> Dict[str, Any]:
    if WEIGHTS_PATH.exists():
        with open(WEIGHTS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "weights": {
            "isolation_forest_anomaly_weight": 0.30,
            "heuristic_domain_weight": 0.70,
            "divergence_penalty_multiplier": 55.0,
            "cost_overrun_penalty_multiplier": 65.0,
            "time_overrun_penalty_multiplier": 18.0,
            "governance_penalty_multiplier": 18.0,
            "evidence_integrity_penalty_multiplier": 18.0,
        }
    }


# ---------------------------------------------------------------------------
# STEP 2a — Feature extraction for IsolationForest
# ---------------------------------------------------------------------------

def _parse_date(raw: Any) -> Optional[datetime]:
    """Safely parse an ISO-8601 date string or date object."""
    if raw is None:
        return None
    try:
        if isinstance(raw, datetime):
            return raw
        s = str(raw).replace("Z", "+00:00")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def extract_isolation_features(project_data: Dict[str, Any]) -> List[float]:
    """
    Build the 5-element numeric feature vector used by IsolationForest.

    Features:
      0  sanctioned_amount        (raw INR float, log-scale invariant inside IF)
      1  expenditure_incurred      (raw INR float)
      2  physical_progress_pct     (normalized 0.0–1.0)
      3  time_elapsed_ratio        (elapsed / planned duration, capped 0–3)
      4  payment_velocity_delta    (expenditure_rate − progress_rate)

    Accepts both snake_case (DB columns) and camelCase (API / JSON) keys so the
    function works identically whether called from the FastAPI route or the
    data-pipeline seeder.
    """
    sanctioned = float(
        project_data.get("sanctioned_amount")
        or project_data.get("sanctionedAmount")
        or 1.0
    )
    expenditure = float(
        project_data.get("expenditure_incurred")
        or project_data.get("expenditureIncurred")
        or 0.0
    )
    raw_prog = float(
        project_data.get("physical_progress_pct")
        or project_data.get("physicalProgressPct")
        or 0.0
    )
    # Normalize to 0–1 regardless of whether stored as 0–100 or 0–1
    norm_prog = (raw_prog / 100.0) if raw_prog > 1.0 else raw_prog
    norm_prog = max(0.0, min(1.0, norm_prog))

    # Time elapsed ratio
    s_raw = (
        project_data.get("date_of_sanction")
        or project_data.get("dateOfSanction")
        or "2024-01-01T00:00:00Z"
    )
    e_raw = (
        project_data.get("expected_completion_date")
        or project_data.get("expectedCompletionDate")
        or "2025-01-01T00:00:00Z"
    )
    a_raw = project_data.get("actual_completion_date") or project_data.get(
        "actualCompletionDate"
    )

    s_dt = _parse_date(s_raw)
    e_dt = _parse_date(e_raw)
    a_dt = _parse_date(a_raw)

    time_ratio = 0.85  # safe fallback
    if s_dt and e_dt:
        now = datetime.now(s_dt.tzinfo)
        end_ref = a_dt if a_dt else now
        total_secs = (e_dt - s_dt).total_seconds()
        if total_secs > 0:
            elapsed = (end_ref - s_dt).total_seconds()
            time_ratio = round(max(0.0, min(3.0, elapsed / total_secs)), 4)

    exp_rate = expenditure / max(1.0, sanctioned)
    vel_delta = round(exp_rate - norm_prog, 4)

    return [sanctioned, expenditure, norm_prog, time_ratio, vel_delta]


# ---------------------------------------------------------------------------
# STEP 2b — IsolationForestAnomalyDetector class
# ---------------------------------------------------------------------------

def _build_synthetic_baseline(n: int = 40, seed: int = 42) -> List[List[float]]:
    """
    Generate a synthetic but statistically representative baseline of
    'normal' MPLADS projects to train IsolationForest when no real peer
    corpus is supplied externally.  Mimics the joint distribution observed
    in the Neon PostgreSQL dataset (AP, KA, MH fiscal years 2022–2026).
    """
    rng = np.random.default_rng(seed)
    X: List[List[float]] = []
    for _ in range(n):
        sanctioned = float(rng.uniform(1_500_000, 9_000_000))
        progress_pct = float(rng.uniform(10.0, 92.0))
        norm_prog = progress_pct / 100.0
        # Expenditure tracks progress closely with small noise
        exp_pct = progress_pct + float(rng.normal(0.0, 3.0))
        exp_pct = max(0.0, min(100.0, exp_pct))
        expenditure = sanctioned * (exp_pct / 100.0)
        # Time ratio roughly mirrors physical progress
        time_ratio = float(
            max(0.0, min(3.0, norm_prog + rng.normal(0.0, 0.06)))
        )
        vel_delta = round((expenditure / max(1.0, sanctioned)) - norm_prog, 4)
        X.append([sanctioned, expenditure, norm_prog, time_ratio, vel_delta])
    return X


class IsolationForestAnomalyDetector:
    """
    Wraps sklearn IsolationForest with:
    - cold-start guard  (< 10 samples → neutral score, INSUFFICIENT_PEER_DATA)
    - logistic score mapping from decision_function() → 0–100 range
    - explicit fit() / score_project() API matching the hybrid engine contract
    """

    # Logistic curve parameters calibrated on the AP pilot dataset:
    # k = steepness, x0 = inflection offset
    _K: float = 20.0
    _X0: float = 0.01

    def __init__(
        self,
        contamination: float = 0.08,
        random_state: int = 42,
        n_estimators: int = 100,
    ) -> None:
        self.contamination = contamination
        self.random_state = random_state
        self.n_estimators = n_estimators
        self.model: Optional[Any] = None  # IsolationForest instance
        self.is_fitted: bool = False
        self.status: str = "UNFITTED"
        self.n_samples: int = 0

    def fit(
        self, projects: Optional[List[Dict[str, Any]]] = None
    ) -> "IsolationForestAnomalyDetector":
        """
        Train on a list of project dicts.  Falls back to a synthetic baseline
        when no external corpus is provided (production cold-start scenario).
        """
        if not _SKLEARN_AVAILABLE:
            self.status = "SKLEARN_UNAVAILABLE"
            return self

        if projects and len(projects) >= 10:
            X = [extract_isolation_features(p) for p in projects]
            self.n_samples = len(X)
        elif projects and len(projects) < 10:
            # Too few real samples — do NOT mix with synthetic to avoid bias
            self.is_fitted = False
            self.status = "INSUFFICIENT_PEER_DATA"
            self.n_samples = len(projects)
            return self
        else:
            # No external corpus → synthetic baseline for cold-start
            X = _build_synthetic_baseline()
            self.n_samples = len(X)

        self.model = _SKIsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=self.n_estimators,
        )
        self.model.fit(X)
        self.is_fitted = True
        self.status = "FITTED"
        return self

    def score_project(
        self, project_data: Dict[str, Any]
    ) -> Tuple[float, str]:
        """
        Returns (isolation_forest_risk_score 0–100, status_label).
        status_label is one of:
          INLIER                  — within statistical peer norms
          OUTLIER                 — extreme multidimensional anomaly (score > 75)
          INSUFFICIENT_PEER_DATA  — fewer than 10 training samples available
          SKLEARN_UNAVAILABLE     — sklearn not installed
        """
        if not self.is_fitted or self.model is None:
            return 0.0, self.status if self.status else "INSUFFICIENT_PEER_DATA"

        features = extract_isolation_features(project_data)
        raw = float(self.model.decision_function([features])[0])

        # Logistic mapping: positive raw → low score (inlier),
        #                   negative raw → high score (outlier)
        score = 100.0 / (1.0 + math.exp(self._K * (raw + self._X0)))
        norm_score = round(max(0.0, min(100.0, score)), 2)

        label = "OUTLIER" if norm_score > 75.0 else "INLIER"
        return norm_score, label

    def explain_project(self, project_data: Dict[str, Any]) -> List[str]:
        """
        Produce human-readable per-feature explanations for why the
        Isolation Forest flagged this project.

        Compares each of the 5 isolation features against the mean and
        standard deviation of the synthetic training baseline, then
        returns only the features that are statistically extreme
        (> 1.5 standard deviations from the baseline mean).

        Returns a list of plain-English explanation strings.
        """
        if not self.is_fitted or self.model is None:
            return []

        try:
            import numpy as np

            # Recompute baseline stats from the training data
            # The training data lives inside the fitted model's estimators
            # We use the synthetic baseline directly for stat comparison
            baseline = _build_synthetic_baseline()
            arr = np.array(baseline)  # shape: (40, 5)

            feature_names = [
                "sanctioned_amount",
                "expenditure_incurred",
                "physical_progress",
                "time_elapsed_ratio",
                "payment_velocity_delta",
            ]
            friendly_names = [
                "Sanctioned amount",
                "Total expenditure",
                "Physical progress",
                "Time elapsed ratio",
                "Payment velocity delta",
            ]

            means = arr.mean(axis=0)
            stds = arr.std(axis=0) + 1e-9  # avoid division by zero

            features = extract_isolation_features(project_data)
            explanations: List[str] = []

            for i, (feat_val, mean, std) in enumerate(zip(features, means, stds)):
                z = (feat_val - mean) / std
                abs_z = abs(z)
                if abs_z < 1.5:
                    continue  # within normal range — skip

                direction = "above" if z > 0 else "below"
                severity = "extremely" if abs_z > 3.0 else ("significantly" if abs_z > 2.0 else "notably")

                if feature_names[i] == "sanctioned_amount":
                    explanations.append(
                        f"Sanctioned amount is {severity} {direction} peer baseline "
                        f"(project scale is an outlier — {round(abs_z, 1)}σ from norm)."
                    )
                elif feature_names[i] == "expenditure_incurred":
                    explanations.append(
                        f"Total expenditure is {severity} {direction} peer-group average "
                        f"({round(abs_z, 1)}σ deviation). "
                        f"{'Disbursement is unusually high for this project size.' if z > 0 else 'Spending is unusually low relative to project scale.'}"
                    )
                elif feature_names[i] == "physical_progress":
                    explanations.append(
                        f"Physical progress reported ({round(features[i]*100, 1)}%) is "
                        f"{severity} {direction} what peer projects show at this stage "
                        f"({round(abs_z, 1)}σ deviation)."
                    )
                elif feature_names[i] == "time_elapsed_ratio":
                    explanations.append(
                        f"Time elapsed ({round(features[i]*100, 1)}% of planned duration) is "
                        f"{severity} {direction} the peer group norm "
                        f"({'significant overrun' if z > 0 else 'ahead of schedule — unusual'}, {round(abs_z, 1)}σ)."
                    )
                elif feature_names[i] == "payment_velocity_delta":
                    if z > 0:
                        explanations.append(
                            f"Payment velocity delta is {severity} positive ({round(features[i], 3)}): "
                            f"funds are flowing {round(abs_z, 1)}σ faster than physical progress justifies — "
                            f"classic ghost-work financial signature."
                        )
                    else:
                        explanations.append(
                            f"Payment velocity delta is {severity} negative ({round(features[i], 3)}): "
                            f"physical progress is {round(abs_z, 1)}σ ahead of disbursement — "
                            f"contractor invoicing appears unusually delayed."
                        )

            return explanations if explanations else [
                "Multi-dimensional statistical outlier detected. No single feature was "
                "extreme enough alone, but the combined pattern across expenditure, "
                "progress, and timeline is statistically rare."
            ]

        except Exception as exc:
            print(f"[IsolationForest] explain_project error: {exc}")
            return ["Statistical outlier detected across combined project metrics."]


# ---------------------------------------------------------------------------
# Module-level singleton detector — trained once on import (warm-up)
# ---------------------------------------------------------------------------

_detector = IsolationForestAnomalyDetector(contamination=0.08).fit()


# ---------------------------------------------------------------------------
# Existing heuristic engine helpers (unchanged API)
# ---------------------------------------------------------------------------

def generate_reasoning(
    features: Dict[str, float], project: Dict[str, Any], risk_score: float
) -> List[Dict[str, str]]:
    findings: List[Dict[str, str]] = []

    # 1. Payment velocity divergence
    div = features["progressExpenditureDivergence"]
    if div > 0.15:
        findings.append({
            "severity": "HIGH" if div > 0.3 else "MODERATE",
            "title": "Expenditure Disproportionate to Ground Progress",
            "explanation": (
                f"Expenditure rate is {round(features['expenditureRate']*100, 1)}% "
                f"while physical progress is only {round(features['progressRate']*100, 1)}% "
                f"(divergence: +{round(div*100, 1)}%)."
            ),
            "evidence": (
                "Financial ledger shows advanced disbursements without "
                "corresponding milestone completion."
            ),
            "module": "FINANCIAL_TEMPORAL",
        })
    elif div < -0.30:
        findings.append({
            "severity": "LOW",
            "title": "Delayed Contractor Invoicing",
            "explanation": (
                f"Physical progress is {round(features['progressRate']*100, 1)}% "
                f"but disbursements are only {round(features['expenditureRate']*100, 1)}%."
            ),
            "evidence": "Works are advancing ahead of bill submission.",
            "module": "FINANCIAL_TEMPORAL",
        })

    # 2. Cost overrun
    if features["costRatio"] > 1.05:
        findings.append({
            "severity": "HIGH" if features["costRatio"] > 1.25 else "MODERATE",
            "title": "Sanction Exceeds Detailed Project Report (DPR)",
            "explanation": (
                f"Sanctioned funds exceed original engineering estimate by "
                f"{round((features['costRatio']-1.0)*100, 1)}%."
            ),
            "evidence": "Technical estimate revised without administrative re-approval.",
            "module": "ADMINISTRATIVE_AUDIT",
        })

    # 3. Timeline overrun / milestone slippage
    if features["timeElapsedRatio"] > 0.9 and features["progressRate"] < 0.95:
        findings.append({
            "severity": "HIGH" if features["timeElapsedRatio"] > 1.3 else "MODERATE",
            "title": "Timeline Overrun / Milestone Slippage",
            "explanation": (
                f"Time elapsed ratio is {round(features['timeElapsedRatio']*100, 1)}% "
                f"of planned duration with incomplete works ({round(features['progressRate']*100, 1)}% completed)."
            ),
            "evidence": (
                "Target completion deadline breached without formal extension granted."
            ),
            "module": "TEMPORAL_MONITOR",
        })
    elif features["timeElapsedRatio"] > 1.1 and features["progressRate"] < 1.0:
        findings.append({
            "severity": "HIGH" if features["timeElapsedRatio"] > 1.5 else "MODERATE",
            "title": "Completion Deadline Exceeded",
            "explanation": (
                f"Contractual deadline has passed (time consumed: {round(features['timeElapsedRatio']*100, 1)}% of schedule) "
                f"with physical progress remaining at {round(features['progressRate']*100, 1)}%."
            ),
            "evidence": (
                "Works remain open past scheduled completion date without official extension on record."
            ),
            "module": "TEMPORAL_MONITOR",
        })

    # 4. Evidence integrity
    if features["evidenceIntegrityScore"] < 0.8:
        findings.append({
            "severity": (
                "HIGH" if features["evidenceIntegrityScore"] < 0.5 else "MODERATE"
            ),
            "title": "Geotagged Photographic Discrepancies",
            "explanation": (
                "Uploaded field verification photos exhibit missing EXIF metadata "
                "or hash duplication."
            ),
            "evidence": (
                "Geo-spatial clustering indicates multiple claims share identical "
                "ground photographs."
            ),
            "module": "VISUAL_SPATIAL",
        })

    # 5. Administrative Escalation
    workflow_status = project.get("workflowStatus") or ""
    if workflow_status in ("ESCALATED", "ESCALATED_STATE"):
        esc_reason = project.get("escalationReason") or "Elevated by district/state authority review."
        findings.append({
            "severity": "HIGH",
            "title": "Active Authority Escalation (Priority Oversight)",
            "explanation": (
                "A District Nodal Officer or State Authority has formally escalated this project "
                "for priority investigation, administrative review, or inquiry."
            ),
            "evidence": (
                f"Workflow status is '{workflow_status}'. Statutory escalation risk floor applied (+75.80 points) "
                f"to ensure priority queue placement. Reason: {esc_reason}"
            ),
            "module": "ADMINISTRATIVE_AUDIT",
        })

    # 6. Incomplete Data Records
    if project.get("dataCompleteness") == "INCOMPLETE":
        findings.append({
            "severity": "HIGH",
            "title": "Statutory Data Incompleteness",
            "explanation": (
                "Essential project documentation or milestone records are missing from the public registry."
            ),
            "evidence": (
                "Missing mandatory statutory telemetry (tender/milestone filings). Project cannot be validated without physical audit."
            ),
            "module": "ADMINISTRATIVE_AUDIT",
        })

    if not findings:
        if risk_score >= 70.0:
            findings.append({
                "severity": "HIGH",
                "title": "Elevated Composite Risk Flag",
                "explanation": "Multiple operational indicators place this project in the high-priority oversight category.",
                "evidence": "Composite audit score exceeded safety threshold. Human verification recommended.",
                "module": "BASELINE_AUDIT",
            })
        elif risk_score >= 40.0:
            findings.append({
                "severity": "MODERATE",
                "title": "Moderate Operational Variance",
                "explanation": "Project telemetry reflects minor milestone or timing variances.",
                "evidence": "Routine field inspection advised during next reporting cycle.",
                "module": "BASELINE_AUDIT",
            })
        else:
            findings.append({
                "severity": "LOW",
                "title": "Normal Operational Parameters",
                "explanation": (
                    "Project telemetry conforms to standard fiscal and physical milestones."
                ),
                "evidence": (
                    "Verified tender, milestone sign-offs, and complete documentation."
                ),
                "module": "BASELINE_AUDIT",
            })

    return findings



# ---------------------------------------------------------------------------
# STEP 3 — Hybrid composite risk score synthesis
# ---------------------------------------------------------------------------

def evaluate_project_risk(project: Dict[str, Any]) -> Dict[str, Any]:
    """
    Computes a hybrid risk score for a single project record.

    Composite formula (weights per roadmap spec):
        composite = (heuristic_penalty × 0.70) + (isolation_forest_score × 0.30)

    UNEXPLAINED_OUTLIER_ANOMALY flag is appended when:
        - isolation_forest_score > 75  (statistically extreme outlier)
        - AND no heuristic rule was triggered (no HIGH/MODERATE finding)

    Return dict keys are identical to the pre-Phase-1 schema so all FastAPI
    routes, response models, and frontend consumers continue to work without
    any changes.
    """
    weights_data = load_weights()
    w = weights_data.get("weights", {})

    # ---- Layer 1: Heuristic domain penalty (0–100) -------------------------
    features = extract_feature_vector(project)

    heuristic_penalty = 0.0

    # Divergence penalty (max 30 pts)
    if features["progressExpenditureDivergence"] > 0.05:
        heuristic_penalty += min(
            30.0,
            (features["progressExpenditureDivergence"] - 0.05)
            * w.get("divergence_penalty_multiplier", 55.0),
        )

    # Cost overrun penalty (max 22 pts)
    if features["costRatio"] > 1.05:
        heuristic_penalty += min(
            22.0,
            (features["costRatio"] - 1.05)
            * w.get("cost_overrun_penalty_multiplier", 65.0),
        )

    # Time overrun penalty (max 22 pts)
    if features["timeElapsedRatio"] > 0.9 and features["progressRate"] < 0.95:
        heuristic_penalty += min(
            22.0,
            max(0.0, features["timeElapsedRatio"] - 0.9) * 18.0
            + (1.0 - features["progressRate"]) * 12.0,
        )

    # Governance compliance penalty (max 18 pts)
    heuristic_penalty += (1.0 - features["governanceComplianceScore"]) * w.get(
        "governance_penalty_multiplier", 18.0
    )

    # Evidence integrity penalty (max 18 pts)
    heuristic_penalty += (1.0 - features["evidenceIntegrityScore"]) * w.get(
        "evidence_integrity_penalty_multiplier", 18.0
    )

    heuristic_score = min(100.0, heuristic_penalty)

    # ---- Layer 2: Isolation Forest score (0–100) ---------------------------
    if_score, if_status = _detector.score_project(project)

    # ---- Layer 3: Visual evidence integrity (0–100) ------------------------
    visual_score = min(
        100.0,
        round((1.0 - features["evidenceIntegrityScore"]) * 80.0 + 15.0, 1),
    )

    # ---- Layer 4: Satellite Sentinel-2 change detection -------------------
    lat = float(project.get("latitude") or project.get("lat") or 17.6868)
    lon = float(project.get("longitude") or project.get("lon") or 83.2185)
    sanction_date = project.get("dateOfSanction") or "2023-01-01"
    current_date = project.get("expectedCompletionDate") or project.get("updatedAt")
    physical_progress = float(
        project.get("physicalProgressPct")
        if project.get("physicalProgressPct") is not None
        else (project.get("physicalProgress") or 0.0)
    )
    work_id = project.get("workId", "UNKNOWN")

    if _SATELLITE_AVAILABLE and analyze_satellite_ground_change:
        sat_result = analyze_satellite_ground_change(
            lat=lat,
            lon=lon,
            sanction_date=sanction_date,
            current_date=current_date,
            physical_progress=physical_progress,
            work_id=work_id,
            force_cloud=bool(project.get("forceCloud")),
            force_ghost=bool(project.get("forceGhost")),
            force_unauthorized=bool(project.get("forceUnauthorized")),
        )
    else:
        sat_result = {
            "status": "SATELLITE_DATA_UNAVAILABLE_CLOUDY",
            "ndbi_delta": 0.0,
            "ndvi_delta": 0.0,
            "t0_date": str(sanction_date),
            "t1_date": str(current_date or datetime.today().date()),
            "cloud_cover_pct": 80.0,
            "satellite_score": None,
            "findings": [],
            "gee_mode": "DETERMINISTIC_MOCK",
        }

    sat_status = sat_result.get("status")
    sat_score = sat_result.get("satellite_score")

    # ---- Hybrid synthesis: Phase 3 50/20/15/15 weights ----------------------
    heur_w = w.get("heuristic_domain_weight", 0.50)
    iso_w = w.get("isolation_forest_anomaly_weight", 0.20)
    vis_w = w.get("visual_spatial_weight", 0.15)
    sat_w = w.get("satellite_spectral_weight", 0.15)

    # Edge Case B (Persistent cloud cover) / Missing Satellite:
    # Do NOT penalize; re-normalize remaining weights dynamically.
    if sat_score is None or sat_status == "SATELLITE_DATA_UNAVAILABLE_CLOUDY":
        rem_w = heur_w + iso_w + vis_w
        raw_score = (
            (heuristic_score * (heur_w / rem_w))
            + (if_score * (iso_w / rem_w))
            + (visual_score * (vis_w / rem_w))
        )
    else:
        raw_score = (
            (heuristic_score * heur_w)
            + (if_score * iso_w)
            + (visual_score * vis_w)
            + (float(sat_score) * sat_w)
        )


    # Data completeness and workflow escalation floors (unchanged from v1)
    completeness = project.get("dataCompleteness", "COMPLETE")
    if completeness == "INCOMPLETE":
        raw_score = max(raw_score, 72.40 + (if_score * 0.145))
    elif completeness == "PARTIAL":
        raw_score = max(raw_score, 38.60 + (if_score * 0.112))

    workflow_status = project.get("workflowStatus", "NORMAL")
    if workflow_status in ("ESCALATED", "ESCALATED_STATE"):
        raw_score = max(raw_score, 75.80 + (if_score * 0.184))

    # Compound floor: when IF marks OUTLIER AND heuristics are also elevated,
    # ensure the project is classified HIGH (floor at 70.0).  This correctly
    # surfaces ghost-work patterns where both signals fire together.
    if if_score > 75.0 and heuristic_score > 50.0:
        raw_score = max(raw_score, 70.0)

    risk_score = round(max(6.40, min(98.60, raw_score)), 2)

    # ---- Risk level --------------------------------------------------------
    if completeness == "INCOMPLETE":
        risk_level = "DATA_INCOMPLETE"
    elif risk_score >= 70.0:
        risk_level = "HIGH"
    elif risk_score >= 40.0:
        risk_level = "MODERATE"
    else:
        risk_level = "LOW"

    # ---- Generate findings -------------------------------------------------
    findings = generate_reasoning(features, project, risk_score)

    # UNEXPLAINED_OUTLIER_ANOMALY:
    # Fired whenever IF score > 75. Calls explain_project() to attach specific
    # per-feature deviation evidence — so this is never a black-box verdict.
    heuristics_fired = any(
        f["severity"] in ("HIGH", "MODERATE") for f in findings
    )
    if if_score > 75.0:
        # Get specific per-feature explanations (z-score deviations from baseline)
        feature_explanations = _detector.explain_project(project)
        heuristic_note = (
            "Heuristic domain rules also independently flagged this project."
            if heuristics_fired
            else "No single domain rule threshold was breached — this is a multi-dimensional pattern."
        )
        # Build a numbered evidence string so each reason is legible
        numbered = " ".join(
            f"[{i+1}] {exp}"
            for i, exp in enumerate(feature_explanations)
        )
        findings.append({
            "severity": "HIGH",
            "title": "Multi-Dimensional Statistical Outlier",
            "explanation": (
                "The Isolation Forest model detected that this project's combined "
                "expenditure, physical progress, and timeline behaviour is statistically "
                "rare among peer MPLADS projects — even if no single rule was individually "
                "breached. This is not a black-box verdict: specific driving factors are "
                "listed in the evidence below."
            ),
            "evidence": (
                f"Anomaly score: {if_score}/100 (peer baseline: {_detector.n_samples} projects). "
                f"{heuristic_note} "
                f"Driving factors — {numbered}"
            ),
            "module": "UNEXPLAINED_OUTLIER_ANOMALY",
        })


    # Append satellite spectral findings (Phase 3)
    for sf in sat_result.get("findings", []):
        if sf.get("title") not in {f["title"] for f in findings}:
            findings.append(sf)

    # ---- Module scores (backward-compatible keys) -------------------------
    return {
        "workId": project.get("workId", "UNKNOWN"),
        "riskScore": risk_score,
        "riskLevel": risk_level,
        # Legacy key — still returned for existing consumers; equals IF score
        "anomalyConfidence": round(if_score / 100.0, 3),
        "features": features,
        "findings": findings,
        "moduleScores": {
            "financialTemporalScore": min(
                100.0, round(heuristic_score * 1.05, 1)
            ),
            "visualSpatialScore": min(
                100.0,
                round((1.0 - features["evidenceIntegrityScore"]) * 80.0 + 15.0, 1),
            ),
            "satelliteScore": round(float(sat_score), 1) if sat_score is not None else None,
        },
        # NEW keys (additive — do not break any existing schema)
        "isolationForestScore": if_score,
        "isolationForestStatus": if_status,
        "peerSampleCount": _detector.n_samples,
        "heuristicScore": round(heuristic_score, 2),
        "satellite_verification": {
            "status": sat_result["status"],
            "ndbi_delta": sat_result["ndbi_delta"],
            "ndvi_delta": sat_result["ndvi_delta"],
            "t0_date": sat_result["t0_date"],
            "t1_date": sat_result["t1_date"],
            "cloud_cover_pct": sat_result["cloud_cover_pct"],
        },
        "satelliteVerification": {
            "status": sat_result["status"],
            "ndbi_delta": sat_result["ndbi_delta"],
            "ndvi_delta": sat_result["ndvi_delta"],
            "t0_date": sat_result["t0_date"],
            "t1_date": sat_result["t1_date"],
            "cloud_cover_pct": sat_result["cloud_cover_pct"],
        },
    }



# ---------------------------------------------------------------------------
# CLI entry-point (unchanged interface)
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="CivicShield ML Risk Inference Engine — Phase 1 (Isolation Forest)"
    )
    parser.add_argument(
        "--predict", type=str, help="Path to project JSON file for inference"
    )
    parser.add_argument(
        "--test", action="store_true", help="Run self-test validation suite"
    )
    args = parser.parse_args()

    if args.test:
        sample = {
            "workId": "TEST-PROJECT-001",
            "estimatedCost": 5_000_000,
            "sanctionedAmount": 5_500_000,
            "expenditureIncurred": 4_800_000,
            "physicalProgressPct": 42.0,
            "dateOfSanction": "2023-01-01T00:00:00Z",
            "expectedCompletionDate": "2024-01-01T00:00:00Z",
            "tenderInvited": True,
            "ucFiled": False,
            "dataCompleteness": "COMPLETE",
        }
        result = evaluate_project_risk(sample)
        print("Self-Test Execution Succeeded:")
        print(json.dumps(result, indent=2))
        assert result["riskScore"] > 50.0, (
            "Expected elevated risk due to expenditure-progress divergence"
        )
        print("ASSERTION PASSED: Risk model correctly flagged divergence anomaly.")
        sys.exit(0)

    if args.predict:
        with open(args.predict, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            results = [evaluate_project_risk(p) for p in data]
        else:
            results = evaluate_project_risk(data)
        print(json.dumps(results, indent=2))
        return

    print("Use --test or --predict <file.json>")


if __name__ == "__main__":
    main()
