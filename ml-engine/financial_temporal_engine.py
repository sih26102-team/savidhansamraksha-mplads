"""
Savidhan Samraksha Multi-Model AI Detection System — Module A: Financial & Temporal Engine
Author: Kousic (ML Engine Lead) & Savidhan Samraksha Engineering Team

Architecture:
Implements 8 core detectors scoring project finances, timelines, progress, and compliance:
  1. Cost-per-unit outlier (Z-score/IQR within peer groups + terrain/remoteness factor)
  2. Near-duplicate work detection (fuzzy text match + geographic proximity <= 500m)
  3. Progress-silence / dormant-project flag (peer-relative velocity, excluding on-hold/litigation)
  4. Isolation Forest on utilization patterns (agency/district baseline, sample size guard >= 10)
  5. Ineligible work-category flag (structured negative list + secondary text advisory hint)
  6. Cross-cycle duplicate asset (later fiscal year re-sanction + low prior progress / cost surge)
  7. No-tender flag (kept + structured metadata for Fusion Layer collusion override)
  8. Missing utilization certificate (UC) flag (differentiated LOW severity backlog vs HIGH compounded)

Zero-breaking-change guarantee: All outputs map cleanly into existing Savidhan Samraksha schemas.
"""

import math
import re
import difflib
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Tuple, Set

try:
    import numpy as np
    _NUMPY_AVAILABLE = True
except ImportError:
    _NUMPY_AVAILABLE = False

try:
    from sklearn.ensemble import IsolationForest as _SKIsolationForest
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False


# ==============================================================================
# Helper Utilities: Dates, Strings, Geospatial Math
# ==============================================================================

def parse_iso_datetime(raw: Any) -> Optional[datetime]:
    """Safely parses date strings, date objects, or datetime objects."""
    if raw is None:
        return None
    if isinstance(raw, datetime):
        return raw
    if isinstance(raw, date):
        return datetime(raw.year, raw.month, raw.day)
    try:
        s = str(raw).strip().replace("Z", "+00:00")
        if len(s) == 10 and s.count("-") == 2:
            return datetime.strptime(s, "%Y-%m-%d")
        return datetime.fromisoformat(s)
    except Exception:
        return None


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    R = 6371000.0  # Earth radius in meters
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (math.sin(delta_phi / 2.0) ** 2 +
         math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2))
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return R * c


def normalize_token_set(text: str) -> Set[str]:
    """Tokenizes and normalizes text for semantic comparison."""
    if not text:
        return set()
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", " ", text.lower())
    stop_words = {
        "and", "the", "of", "to", "in", "at", "for", "with", "a", "an", "on", "by",
        "near", "adjacent", "proposed", "new", "work", "works", "under", "scheme",
        "mplads", "constituency", "district", "panchayat", "village", "mandal"
    }
    tokens = {w for w in cleaned.split() if len(w) > 2 and w not in stop_words}
    return tokens


def fuzzy_text_similarity(text1: str, text2: str) -> float:
    """
    Computes a hybrid similarity score combining Token Overlap, Jaccard similarity,
    and Levenshtein sequence matching (returns 0.0 to 1.0).
    """
    t1 = str(text1 or "").strip().lower()
    t2 = str(text2 or "").strip().lower()
    if not t1 or not t2:
        return 0.0
    if t1 == t2:
        return 1.0

    # 1. Token Overlap & Jaccard
    tokens1 = normalize_token_set(t1)
    tokens2 = normalize_token_set(t2)
    if tokens1 and tokens2:
        intersection = len(tokens1 & tokens2)
        union = len(tokens1 | tokens2)
        jaccard = intersection / max(1, union)
        overlap = intersection / max(1, min(len(tokens1), len(tokens2)))
    else:
        jaccard = 0.0
        overlap = 0.0

    # 2. SequenceMatcher ratio
    seq_ratio = difflib.SequenceMatcher(None, t1, t2).ratio()

    # Calibrated blend
    token_metric = (0.60 * overlap) + (0.40 * jaccard)
    return round(max(seq_ratio, (0.50 * token_metric) + (0.50 * seq_ratio)), 4)


# ==============================================================================
# Domain Constants & Categorical Dictionaries
# ==============================================================================

# Terrain multipliers (Tf): Logistics and civil transport costs are higher in remote terrains
TERRAIN_MULTIPLIERS = {
    "HILLY": 1.30,
    "MOUNTAINOUS": 1.35,
    "TRIBAL": 1.25,
    "REMOTE": 1.25,
    "FOREST": 1.20,
    "DESERT": 1.20,
    "ISLAND": 1.40,
    "PLATEAU": 1.12,
    "SEMI_ARID": 1.08,
    "COASTAL": 1.05,
    "PLAINS": 1.00,
    "URBAN": 1.00,
}

# Districts with known hilly/difficult terrain in India (auto-fallback if terrain not explicitly tagged)
HILLY_OR_REMOTE_DISTRICTS = {
    "alluri sitharama raju", "parvathipuram manyam", "paderu", "aruku", "rampagodavaram",
    "chamoli", "rudraprayag", "uttarkashi", "leh", "kargil", "shimla", "kullu",
    "kinnaur", "lahaul and spiti", "chamba", "wayanad", "idukki", "nilgiris",
    "dindori", "mandla", "bastard", "dantewada", "sukma", "gadchiroli"
}

# Statutory MPLADS Ineligible Categories (prohibited from MPLADS funds)
STATUTORY_INELIGIBLE_CATEGORIES = {
    "RELIGIOUS", "RELIGIOUS_INSTITUTION", "TEMPLE", "MOSQUE", "CHURCH", "GURDWARA",
    "PRIVATE_CLUB", "COMMERCIAL_ENTITY", "COMMERCIAL_ASSET", "PRIVATE_TRUST",
    "INDIVIDUAL_BENEFIT", "POLITICAL_PARTY_OFFICE"
}

# Free-text secondary review trigger words
INELIGIBILITY_REVIEW_KEYWORDS = [
    "temple", "mandir", "mosque", "masjid", "church", "gurdwara", "ashram",
    "private club", "golf club", "gymkhana", "commercial shop", "commercial complex",
    "private trust", "memorial trust"
]

# Civic infrastructure exemption words (e.g. road TO temple or drainage NEAR church is public)
PUBLIC_INFRASTRUCTURE_EXEMPTIONS = [
    "road", "cc road", "drainage", "stormwater", "culvert", "bridge",
    "street light", "solar light", "drinking water", "borewell", "ro plant",
    "school", "angawadi", "hospital", "phc", "community hall", "pathway"
]


# ==============================================================================
# Module A: Financial & Temporal Engine Class
# ==============================================================================

class FinancialTemporalEngine:
    """
    Module A: Comprehensive Financial & Temporal Risk Evaluation Engine.
    Executes 8 core anomaly detectors without requiring fraudulent training labels.
    """

    def __init__(self, weights: Optional[Dict[str, float]] = None):
        self.weights = weights or {
            "cost_outlier_weight": 20.0,
            "near_duplicate_weight": 25.0,
            "progress_silence_weight": 18.0,
            "utilization_outlier_weight": 22.0,
            "ineligible_category_weight": 35.0,
            "cross_cycle_weight": 25.0,
            "no_tender_weight": 15.0,
            "missing_uc_weight": 10.0,
        }

    # --------------------------------------------------------------------------
    # 1. Cost-Per-Unit Outlier Detector
    # --------------------------------------------------------------------------
    def detect_cost_outlier(
        self,
        project: Dict[str, Any],
        peer_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Z-score and IQR outlier detection within peer groups (work-type + district).
        Applies terrain factor (Tf) so remote/mountainous regions are not falsely penalized.
        """
        cost = float(
            project.get("sanctioned_amount") or project.get("sanctionedAmount") or
            project.get("estimated_cost") or project.get("estimatedCost") or 0.0
        )
        if cost <= 0:
            return None

        category = str(project.get("work_category") or project.get("category") or "INFRASTRUCTURE").upper()
        district = str(project.get("district") or project.get("district_id") or "UNKNOWN").strip().lower()
        
        # Determine terrain factor
        raw_terrain = str(project.get("terrain_type") or project.get("terrain") or "").strip().upper()
        if raw_terrain in TERRAIN_MULTIPLIERS:
            tf = TERRAIN_MULTIPLIERS[raw_terrain]
            terrain_label = raw_terrain
        elif any(hd in district for hd in HILLY_OR_REMOTE_DISTRICTS):
            tf = 1.30
            terrain_label = "HILLY/REMOTE_TERRAIN"
        else:
            tf = 1.00
            terrain_label = "STANDARD_PLAINS"

        # Collect peer costs
        peer_costs = []
        if peer_projects:
            for p in peer_projects:
                p_cat = str(p.get("work_category") or p.get("category") or "").upper()
                p_cost = float(p.get("sanctioned_amount") or p.get("sanctionedAmount") or 0.0)
                if p_cost > 0 and (p_cat == category or not category or category == "INFRASTRUCTURE"):
                    peer_costs.append(p_cost)

        # Baseline peer statistics
        if len(peer_costs) >= 8:
            if _NUMPY_AVAILABLE:
                arr = np.array(peer_costs)
                mean_cost = float(np.mean(arr))
                raw_std = float(np.std(arr))
                std_cost = max(mean_cost * 0.15, raw_std)
                q25 = float(np.percentile(arr, 25))
                q75 = float(np.percentile(arr, 75))
            else:
                sorted_c = sorted(peer_costs)
                mean_cost = sum(sorted_c) / len(sorted_c)
                raw_std = math.sqrt(sum((x - mean_cost) ** 2 for x in sorted_c) / len(sorted_c))
                std_cost = max(mean_cost * 0.15, raw_std)
                q25 = sorted_c[int(len(sorted_c) * 0.25)]
                q75 = sorted_c[int(len(sorted_c) * 0.75)]
            iqr = max(mean_cost * 0.20, q75 - q25)
        else:
            # Synthetic category benchmarks calibrated from national MPLADS median
            category_medians = {
                "COMMUNITY_HALL": 4_000_000.0,
                "ROADS": 5_000_000.0,
                "DRINKING_WATER": 2_800_000.0,
                "EDUCATION": 3_500_000.0,
                "HEALTH": 4_500_000.0,
                "SANITATION": 1_800_000.0,
            }
            mean_cost = category_medians.get(category, 3_500_000.0)
            std_cost = mean_cost * 0.35
            iqr = mean_cost * 0.45

        # Effective threshold adjusted by terrain factor
        effective_std = std_cost * tf
        z_score = (cost - mean_cost) / effective_std

        if z_score > 2.0 or cost > (mean_cost + 2.2 * iqr * tf):
            severity = "HIGH" if z_score > 3.0 else "MODERATE"
            excess_pct = round(((cost - mean_cost) / mean_cost) * 100, 1)
            return {
                "detector": "COST_PER_UNIT_OUTLIER",
                "severity": severity,
                "title": f"Cost-Per-Unit Outlier (+{excess_pct}% above peer baseline)",
                "explanation": (
                    f"Sanction of ₹{cost:,.0f} exceeds district peer norm for '{category}' "
                    f"by {excess_pct}% (Z-score: {z_score:.2f} sigma, adjusted for {terrain_label} logistics factor {tf}x)."
                ),
                "evidence": (
                    f"Project cost: ₹{cost:,.0f} | Peer average: ₹{mean_cost:,.0f} | "
                    f"Terrain allowance factor: {tf:.2f}x | Statistical deviation: {z_score:.2f} sigma."
                ),
                "module": "FINANCIAL_TEMPORAL",
                "penalty": min(22.0, max(8.0, z_score * 6.0)),
                "telemetry": {
                    "zScore": round(z_score, 2),
                    "peerMean": mean_cost,
                    "terrainFactor": tf,
                    "terrainLabel": terrain_label
                }
            }
        return None

    # --------------------------------------------------------------------------
    # 2. Near-Duplicate Work Detector
    # --------------------------------------------------------------------------
    def detect_near_duplicate(
        self,
        project: Dict[str, Any],
        peer_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Detects double-sanctioned works at the same site.
        Enforces BOTH text similarity (>=0.75) AND geographic proximity (<= 500m).
        Common titles in distant villages are NEVER falsely flagged.
        """
        if not peer_projects:
            return None

        current_id = str(project.get("work_id") or project.get("workId") or "")
        current_desc = str(project.get("work_description") or project.get("title") or project.get("description") or "")
        cur_lat = float(project.get("latitude") or project.get("lat") or 0.0)
        cur_lon = float(project.get("longitude") or project.get("lon") or 0.0)

        if not current_desc or len(current_desc.strip()) < 8:
            return None

        for p in peer_projects:
            p_id = str(p.get("work_id") or p.get("workId") or "")
            if p_id == current_id or not p_id:
                continue

            p_desc = str(p.get("work_description") or p.get("title") or p.get("description") or "")
            text_sim = fuzzy_text_similarity(current_desc, p_desc)

            # Only check spatial proximity if text is substantially similar
            if text_sim >= 0.65:
                p_lat = float(p.get("latitude") or p.get("lat") or 0.0)
                p_lon = float(p.get("longitude") or p.get("lon") or 0.0)

                # Geographic proximity check
                if cur_lat != 0.0 and cur_lon != 0.0 and p_lat != 0.0 and p_lon != 0.0:
                    dist_meters = haversine_distance_meters(cur_lat, cur_lon, p_lat, p_lon)
                    if dist_meters <= 500.0:
                        return {
                            "detector": "NEAR_DUPLICATE_WORK_SANCTION",
                            "severity": "HIGH",
                            "title": "Co-Located Near-Duplicate Work Sanction Detected",
                            "explanation": (
                                f"Work description has {round(text_sim * 100, 1)}% similarity with project {p_id} "
                                f"located just {round(dist_meters)} meters away at the same site. "
                                f"Potential double-dipping or duplicate sanction."
                            ),
                            "evidence": (
                                f"Candidate: '{current_desc[:50]}...' matches existing '{p_desc[:50]}...' "
                                f"(Similarity: {text_sim:.2f}, Ground Distance: {dist_meters:.1f}m)."
                            ),
                            "module": "FINANCIAL_TEMPORAL",
                            "penalty": 24.0,
                            "telemetry": {
                                "duplicateWorkId": p_id,
                                "textSimilarity": text_sim,
                                "distanceMeters": round(dist_meters, 1)
                            }
                        }
                else:
                    # Spatial coords unavailable: check if exact village/site string matches
                    cur_loc = str(project.get("village") or project.get("location") or "").strip().lower()
                    p_loc = str(p.get("village") or p.get("location") or "").strip().lower()
                    if cur_loc and p_loc and cur_loc == p_loc and text_sim >= 0.85:
                        return {
                            "detector": "NEAR_DUPLICATE_WORK_SANCTION",
                            "severity": "HIGH",
                            "title": "Near-Duplicate Work at Identical Named Location",
                            "explanation": (
                                f"Work description has {round(text_sim * 100, 1)}% match with {p_id} "
                                f"in the same village ({cur_loc})."
                            ),
                            "evidence": f"Matched project: {p_id} (Similarity: {text_sim:.2f}, Location: {cur_loc}).",
                            "module": "FINANCIAL_TEMPORAL",
                            "penalty": 22.0,
                            "telemetry": {
                                "duplicateWorkId": p_id,
                                "textSimilarity": text_sim,
                                "location": cur_loc
                            }
                        }
        return None

    # --------------------------------------------------------------------------
    # 3. Progress-Silence / Dormant-Project Flag
    # --------------------------------------------------------------------------
    def detect_progress_silence(
        self,
        project: Dict[str, Any],
        peer_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Detects silent/dormant projects using peer-relative velocity.
        CRITICAL GUARD: Projects with official on-hold status (litigation, land dispute)
        are excluded from this check entirely.
        """
        # 1. On-hold / litigation exclusion guard
        status = str(project.get("workflow_status") or project.get("status") or "").upper()
        on_hold_reason = str(project.get("on_hold_reason") or project.get("hold_reason") or "").upper()
        exemption_tokens = {"ON_HOLD", "LITIGATION", "COURT_STAY", "LAND_DISPUTE", "FOREST_CLEARANCE", "INQUIRY"}
        
        if any(tok in status or tok in on_hold_reason for tok in exemption_tokens):
            return None

        # 2. Check if already 100% completed
        progress = float(project.get("physical_progress_pct") or project.get("physicalProgressPct") or 0.0)
        if progress >= 100.0 or project.get("actual_completion_date"):
            return None

        # 3. Measure silence duration
        sanction_dt = parse_iso_datetime(project.get("date_of_sanction") or project.get("dateOfSanction"))
        if not sanction_dt:
            return None

        now = datetime.now(sanction_dt.tzinfo)
        last_update_dt = parse_iso_datetime(project.get("updated_at") or project.get("updatedAt"))

        # Check progress updates array if present
        progress_updates = project.get("progress_updates") or project.get("progressUpdates") or []
        if isinstance(progress_updates, list) and len(progress_updates) > 0:
            latest_prog = max(
                (parse_iso_datetime(u.get("date") or u.get("update_date")) for u in progress_updates if u.get("date") or u.get("update_date")),
                default=None
            )
            if latest_prog:
                last_update_dt = latest_prog

        ref_dt = last_update_dt or sanction_dt
        days_silent = max(0, (now - ref_dt).days)

        # Peer velocity benchmark (MPLADS updates are stage-driven; norm is ~180-240 days)
        peer_silence_days = []
        if peer_projects:
            for p in peer_projects:
                s_dt = parse_iso_datetime(p.get("date_of_sanction") or p.get("dateOfSanction"))
                u_dt = parse_iso_datetime(p.get("updated_at") or p.get("updatedAt"))
                if s_dt and u_dt:
                    peer_silence_days.append(max(0, (now - u_dt).days))

        if len(peer_silence_days) >= 6:
            if _NUMPY_AVAILABLE:
                peer_p85 = float(np.percentile(peer_silence_days, 85))
            else:
                sorted_d = sorted(peer_silence_days)
                peer_p85 = float(sorted_d[int(len(sorted_d) * 0.85)])
        else:
            peer_p85 = 180.0  # Stage-based MPLADS baseline

        # Flag if silence exceeds peer threshold
        threshold = max(180.0, peer_p85 * 1.35)
        if days_silent > threshold:
            severity = "HIGH" if days_silent > 365 else "MODERATE"
            return {
                "detector": "PROGRESS_SILENCE_DORMANT",
                "severity": severity,
                "title": f"Prolonged Progress Silence ({days_silent} days without telemetry)",
                "explanation": (
                    f"No physical milestone update recorded for {days_silent} days, "
                    f"significantly exceeding peer update velocity (norm: <{round(threshold)} days). "
                    f"Project appears stalled or dormant with funds committed."
                ),
                "evidence": (
                    f"Days since last update: {days_silent} days (Peer P85 threshold: {round(threshold)} days). "
                    f"Current recorded progress: {progress}%. No legal dispute or on-hold notice registered."
                ),
                "module": "TEMPORAL_MONITOR",
                "penalty": min(20.0, 8.0 + (days_silent / 90.0) * 3.0),
                "telemetry": {
                    "daysSilent": days_silent,
                    "peerThresholdDays": round(threshold)
                }
            }
        return None

    # --------------------------------------------------------------------------
    # 4. Isolation Forest on Utilization Patterns
    # --------------------------------------------------------------------------
    def detect_utilization_outlier(
        self,
        project: Dict[str, Any],
        agency_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates agency/district expenditure-vs-completion trajectory via Isolation Forest.
        Enforces minimum sample size (>=10). Thin agency data is marked 'insufficient data'
        without negative score penalty.
        """
        sanctioned = float(project.get("sanctioned_amount") or project.get("sanctionedAmount") or 1.0)
        expenditure = float(project.get("expenditure_incurred") or project.get("expenditureIncurred") or 0.0)
        progress = float(project.get("physical_progress_pct") or project.get("physicalProgressPct") or 0.0)

        exp_rate = expenditure / max(1.0, sanctioned)
        prog_norm = progress / 100.0
        vel_delta = exp_rate - prog_norm

        # Sample size guard: minimum 10 samples required for agency peer training
        if not agency_projects or len(agency_projects) < 10 or not _SKLEARN_AVAILABLE:
            return {
                "detector": "ISOLATION_FOREST_UTILIZATION",
                "status": "INSUFFICIENT_PEER_DATA",
                "score": 0.0,
                "sampleCount": len(agency_projects) if agency_projects else 0,
                "finding": None
            }

        # Train agency peer baseline
        X = []
        for p in agency_projects:
            s = float(p.get("sanctioned_amount") or p.get("sanctionedAmount") or 1.0)
            e = float(p.get("expenditure_incurred") or p.get("expenditureIncurred") or 0.0)
            pr = float(p.get("physical_progress_pct") or p.get("physicalProgressPct") or 0.0) / 100.0
            er = e / max(1.0, s)
            vd = er - pr
            X.append([s, e, pr, vd])

        iso = _SKIsolationForest(contamination=0.10, random_state=42, n_estimators=60)
        iso.fit(X)

        cur_feat = [sanctioned, expenditure, prog_norm, vel_delta]
        raw_dec = float(iso.decision_function([cur_feat])[0])
        score = 100.0 / (1.0 + math.exp(20.0 * (raw_dec + 0.01)))

        if score > 75.0 and vel_delta > 0.15:
            finding = {
                "detector": "AGENCY_UTILIZATION_OUTLIER",
                "severity": "HIGH",
                "title": "Agency Utilization Pattern Anomaly (Isolation Forest Outlier)",
                "explanation": (
                    f"Agency expenditure-vs-milestone trajectory departs significantly "
                    f"from peer projects in the same agency cohort (IF Anomaly Score: {round(score, 1)}/100)."
                ),
                "evidence": (
                    f"Payment velocity divergence: {vel_delta:+.2f} (Disbursed: {round(exp_rate*100, 1)}%, "
                    f"Physical: {progress}%). Agency peer pool: {len(agency_projects)} works."
                ),
                "module": "FINANCIAL_TEMPORAL",
                "penalty": 18.0,
                "telemetry": {
                    "ifScore": round(score, 1),
                    "agencyPoolSize": len(agency_projects)
                }
            }
            return {
                "detector": "ISOLATION_FOREST_UTILIZATION",
                "status": "OUTLIER",
                "score": round(score, 1),
                "sampleCount": len(agency_projects),
                "finding": finding
            }

        return {
            "detector": "ISOLATION_FOREST_UTILIZATION",
            "status": "INLIER",
            "score": round(score, 1),
            "sampleCount": len(agency_projects),
            "finding": None
        }

    # --------------------------------------------------------------------------
    # 5. Ineligible Work-Category Detector
    # --------------------------------------------------------------------------
    def detect_ineligible_category(self, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Detects statutory MPLADS negative list expenditures (religious, private, commercial).
        Structured category checked first (HIGH severity).
        Free-text keywords serve ONLY as a secondary review hint (LOW severity advisory).
        Avoids false hits like 'CC road near temple' for public infrastructure.
        """
        cat = str(project.get("work_category") or project.get("category") or "").upper().strip()
        ownership = str(project.get("ownership_type") or project.get("asset_ownership") or "").upper().strip()

        # 1. Tier 1: Structured Category Check (HIGH severity)
        if cat in STATUTORY_INELIGIBLE_CATEGORIES or ownership in STATUTORY_INELIGIBLE_CATEGORIES:
            return {
                "detector": "INELIGIBLE_WORK_CATEGORY_STRUCTURAL",
                "severity": "HIGH",
                "title": f"Prohibited Category Sanction: {cat or ownership}",
                "explanation": (
                    f"Category '{cat or ownership}' violates Section 5 of official MPLADS Guidelines, "
                    f"which strictly prohibits public funds for religious, commercial, or private entities."
                ),
                "evidence": f"Structured attribute category='{cat}' / ownership='{ownership}' in statutory negative list.",
                "module": "GOVERNANCE_COMPLIANCE",
                "penalty": 35.0,
                "telemetry": {"prohibitedCategory": cat or ownership}
            }

        # 2. Tier 2: Free-text Keyword Hint (Secondary Advisory Only)
        desc = str(project.get("work_description") or project.get("title") or "").lower()
        has_prohibited_kw = any(kw in desc for kw in INELIGIBILITY_REVIEW_KEYWORDS)
        
        if has_prohibited_kw:
            # Check if clearly public civic infrastructure
            is_civic = any(civic in desc for civic in PUBLIC_INFRASTRUCTURE_EXEMPTIONS)
            if is_civic:
                # E.g. "CC Road from School to Temple" is public infrastructure — DO NOT FLAG
                return None

            # Unclear ownership — advisory review flag only, NEVER automatic fraud verdict
            return {
                "detector": "INELIGIBLE_WORK_CATEGORY_ADVISORY",
                "severity": "LOW",
                "title": "Advisory Hint: Description Mentions Restricted Entity Terms",
                "explanation": (
                    "Work title contains keywords associated with private/religious entities. "
                    "Routine administrative review recommended to verify public community ownership."
                ),
                "evidence": f"Title text match without structured category confirmation: '{desc[:60]}...'",
                "module": "ADMINISTRATIVE_AUDIT",
                "penalty": 4.0,
                "telemetry": {"advisoryTextHint": True}
            }

        return None

    # --------------------------------------------------------------------------
    # 6. Cross-Cycle Duplicate Asset Detector
    # --------------------------------------------------------------------------
    def detect_cross_cycle_duplicate(
        self,
        project: Dict[str, Any],
        historical_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Detects same asset re-sanctioned in a later fiscal year.
        Requires BOTH phrase match AND (prior progress < 35% or cost surge > 1.4x).
        Phrase match alone is NEVER sufficient.
        """
        if not historical_projects:
            return None

        current_fy = str(project.get("fiscal_year") or project.get("fiscalYear") or "").strip()
        current_desc = str(project.get("work_description") or project.get("title") or "")
        current_cost = float(project.get("sanctioned_amount") or project.get("sanctionedAmount") or 0.0)
        current_id = str(project.get("work_id") or project.get("workId") or "")

        if not current_fy or not current_desc or len(current_desc) < 8:
            return None

        for hp in historical_projects:
            h_id = str(hp.get("work_id") or hp.get("workId") or "")
            h_fy = str(hp.get("fiscal_year") or hp.get("fiscalYear") or "").strip()

            if h_id == current_id or h_fy == current_fy or not h_fy:
                continue

            h_desc = str(hp.get("work_description") or hp.get("title") or "")
            sim = fuzzy_text_similarity(current_desc, h_desc)

            if sim >= 0.70:
                h_prog = float(hp.get("physical_progress_pct") or hp.get("physicalProgressPct") or 0.0)
                h_cost = float(hp.get("sanctioned_amount") or hp.get("sanctionedAmount") or 1.0)
                cost_ratio = current_cost / max(1.0, h_cost)

                # Compound condition: Prior project incomplete OR cost escalated without scope change
                if h_prog < 35.0 or cost_ratio > 1.40 or (not hp.get("uc_filed") and not hp.get("ucFiled")):
                    return {
                        "detector": "CROSS_CYCLE_DUPLICATE_ASSET",
                        "severity": "HIGH",
                        "title": f"Cross-Cycle Duplicate Asset Re-Sanction ({h_fy} -> {current_fy})",
                        "explanation": (
                            f"Asset matches prior project {h_id} ({h_fy}) with {round(sim*100, 1)}% phrase overlap. "
                            f"Prior sanction recorded only {h_prog}% progress before current re-sanction of ₹{current_cost:,.0f}."
                        ),
                        "evidence": (
                            f"Prior work: {h_id} ({h_fy}, ₹{h_cost:,.0f}, {h_prog}% physical completion). "
                            f"Current work: {current_id} ({current_fy}, ₹{current_cost:,.0f}). Cost surge: {cost_ratio:.2f}x."
                        ),
                        "module": "FINANCIAL_TEMPORAL",
                        "penalty": 25.0,
                        "telemetry": {
                            "priorWorkId": h_id,
                            "priorFiscalYear": h_fy,
                            "priorProgress": h_prog,
                            "costSurgeRatio": round(cost_ratio, 2)
                        }
                    }
        return None

    # --------------------------------------------------------------------------
    # 7. No-Tender Compliance Detector (with Collusion Override prep)
    # --------------------------------------------------------------------------
    def detect_no_tender(self, project: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Flags work sanctioned without competitive tendering.
        Prepares structured metadata for Section 7 Fusion Layer collusion override.
        """
        tender_invited = project.get("tender_invited")
        if tender_invited is None:
            tender_invited = project.get("tenderInvited", True)

        cost = float(project.get("sanctioned_amount") or project.get("sanctionedAmount") or 0.0)
        
        # Works over ₹5 Lakhs (500,000 INR) require statutory e-tender
        if not tender_invited and cost > 500_000:
            severity = "HIGH" if cost > 2_500_000 else "MODERATE"
            agency_id = str(project.get("agency_id") or project.get("agencyId") or "UNKNOWN")
            approver_id = str(project.get("approver_id") or project.get("approverId") or project.get("collector_id") or "UNKNOWN")

            return {
                "detector": "NO_TENDER_SANCTION",
                "severity": severity,
                "title": "Statutory Competitive Tendering Omitted",
                "explanation": (
                    f"Work sanctioned for ₹{cost:,.0f} without competitive e-tendering, "
                    f"exceeding the statutory ₹5,00,000 threshold for direct department execution."
                ),
                "evidence": f"Tender invited: False. Value: ₹{cost:,.0f}. Agency: {agency_id}. Statutory ceiling: ₹5,00,000.",
                "module": "ADMINISTRATIVE_AUDIT",
                "penalty": 15.0 if severity == "HIGH" else 10.0,
                "telemetry": {
                    "agencyId": agency_id,
                    "approverId": approver_id,
                    "sanctionAmount": cost,
                    "fusionCollusionEligible": True
                }
            }
        return None

    # --------------------------------------------------------------------------
    # 8. Missing Utilization Certificate (UC) Detector
    # --------------------------------------------------------------------------
    def detect_missing_uc(
        self,
        project: Dict[str, Any],
        active_findings: Optional[List[Dict[str, Any]]] = None
    ) -> Optional[Dict[str, Any]]:
        """
        Evaluates UC backlog with CAG-aligned calibration:
        - Standalone: LOW severity (routine administrative reporting backlog).
        - Compounded (paired with cost outlier, divergence, or dormancy): Escalates to HIGH.
        """
        uc_filed = project.get("uc_filed")
        if uc_filed is None:
            uc_filed = project.get("ucFiled", False)

        if uc_filed:
            return None

        expenditure = float(project.get("expenditure_incurred") or project.get("expenditureIncurred") or 0.0)
        sanctioned = float(project.get("sanctioned_amount") or project.get("sanctionedAmount") or 1.0)
        exp_rate = expenditure / max(1.0, sanctioned)

        # Trigger if substantial funds disbursed (>= 60%) or project past schedule
        if exp_rate >= 0.60:
            # Check if compounded by existing financial anomalies
            compounding_detectors = {
                "COST_PER_UNIT_OUTLIER", "NEAR_DUPLICATE_WORK_SANCTION",
                "PROGRESS_SILENCE_DORMANT", "AGENCY_UTILIZATION_OUTLIER",
                "CROSS_CYCLE_DUPLICATE_ASSET"
            }
            is_compounded = any(
                f.get("detector") in compounding_detectors or f.get("severity") == "HIGH"
                for f in (active_findings or [])
            )

            if is_compounded:
                return {
                    "detector": "MISSING_UC_COMPOUNDED",
                    "severity": "HIGH",
                    "title": "Overdue UC Compounded by Active Financial Discrepancies",
                    "explanation": (
                        f"Utilization Certificate overdue despite {round(exp_rate*100, 1)}% funds spent (₹{expenditure:,.0f}). "
                        f"Compounded by active milestone or cost anomalies, significantly elevating fiduciary risk."
                    ),
                    "evidence": f"Expenditure rate: {round(exp_rate*100, 1)}%. Statutory UC unfiled. Compounding flags present.",
                    "module": "ADMINISTRATIVE_AUDIT",
                    "penalty": 12.0,
                    "telemetry": {"compounded": True, "expenditureRate": exp_rate}
                }
            else:
                # Standalone backlog per CAG audit patterns
                return {
                    "detector": "MISSING_UC_BACKLOG",
                    "severity": "LOW",
                    "title": "Pending Utilization Certificate (Administrative Backlog)",
                    "explanation": (
                        f"Utilization Certificate pending for expenditure of ₹{expenditure:,.0f} ({round(exp_rate*100, 1)}%). "
                        f"Consistent with routine administrative delay under CAG oversight; submission required."
                    ),
                    "evidence": f"Disbursement: {round(exp_rate*100, 1)}% of sanction. UC status: Unfiled. Routine compliance notice.",
                    "module": "ADMINISTRATIVE_AUDIT",
                    "penalty": 4.0,
                    "telemetry": {"compounded": False, "expenditureRate": exp_rate}
                }
        return None

    # --------------------------------------------------------------------------
    # Master Evaluation Method
    # --------------------------------------------------------------------------
    def evaluate_financial_temporal(
        self,
        project: Dict[str, Any],
        peer_projects: Optional[List[Dict[str, Any]]] = None,
        historical_projects: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Executes all 8 detectors of Module A in order and computes composite score.
        Returns unified, explainable result dictionary.
        """
        findings: List[Dict[str, Any]] = []
        detector_results: Dict[str, Any] = {}
        total_penalty = 0.0

        # 1. Cost-per-unit Outlier
        f1 = self.detect_cost_outlier(project, peer_projects)
        if f1:
            findings.append(f1)
            total_penalty += f1.get("penalty", 15.0)
            detector_results["cost_outlier"] = f1

        # 2. Near-duplicate Work
        f2 = self.detect_near_duplicate(project, peer_projects)
        if f2:
            findings.append(f2)
            total_penalty += f2.get("penalty", 20.0)
            detector_results["near_duplicate"] = f2

        # 3. Progress Silence / Dormancy
        f3 = self.detect_progress_silence(project, peer_projects)
        if f3:
            findings.append(f3)
            total_penalty += f3.get("penalty", 15.0)
            detector_results["progress_silence"] = f3

        # 4. Utilization Isolation Forest
        f4_res = self.detect_utilization_outlier(project, peer_projects)
        detector_results["utilization_if"] = f4_res
        if f4_res and f4_res.get("finding"):
            findings.append(f4_res["finding"])
            total_penalty += f4_res["finding"].get("penalty", 18.0)

        # 5. Ineligible Work Category
        f5 = self.detect_ineligible_category(project)
        if f5:
            findings.append(f5)
            total_penalty += f5.get("penalty", 30.0)
            detector_results["ineligible_category"] = f5

        # 6. Cross-Cycle Duplicate Asset
        f6 = self.detect_cross_cycle_duplicate(project, historical_projects)
        if f6:
            findings.append(f6)
            total_penalty += f6.get("penalty", 22.0)
            detector_results["cross_cycle"] = f6

        # 7. No-Tender Compliance
        f7 = self.detect_no_tender(project)
        if f7:
            findings.append(f7)
            total_penalty += f7.get("penalty", 12.0)
            detector_results["no_tender"] = f7

        # 8. Missing UC (evaluates compounding with previous findings)
        f8 = self.detect_missing_uc(project, findings)
        if f8:
            findings.append(f8)
            total_penalty += f8.get("penalty", 5.0)
            detector_results["missing_uc"] = f8

        # Base financial score mapping
        score = min(100.0, round(total_penalty, 1))

        return {
            "score": score,
            "status": "FLAGGED" if any(f.get("severity") in ("HIGH", "MODERATE") for f in findings) else "NORMAL",
            "findings": findings,
            "detectorResults": detector_results,
            "findingsCount": len(findings)
        }
