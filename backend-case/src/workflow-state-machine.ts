/**
 * Hierarchical Workflow State Machine & Role Permission Matrix
 * Author: Poornesh (Case Management Lead)
 */

export type AuthorityRole =
  | "DISTRICT_COLLECTOR"
  | "STATE_NODAL_OFFICER"
  | "CENTRAL_OVERSIGHT"
  | "CAG_AUDITOR"
  | "ANTI_CORRUPTION_BUREAU"
  | "IMPLEMENTING_AGENCY"
  | "PUBLIC_CITIZEN";

export type CaseWorkflowStatus =
  | "NORMAL"
  | "FLAGGED"
  | "ESCALATED_DISTRICT"
  | "ESCALATED_STATE"
  | "ESCALATED_NATIONAL"
  | "SANCTION_FROZEN"
  | "UNDER_INQUIRY"
  | "RESOLVED"
  | "DISMISSED";

export type WorkflowAction =
  | "FLAG_FOR_INSPECTION"
  | "ESCALATE_TO_STATE"
  | "ESCALATE_TO_NATIONAL"
  | "FREEZE_SANCTION"
  | "ORDER_INQUIRY"
  | "RESOLVE_CASE"
  | "DISMISS_FLAG"
  | "SUBMIT_EXPLANATION"
  | "REQUEST_EXTENSION";

export interface StateTransitionResult {
  allowed: boolean;
  nextStatus?: CaseWorkflowStatus;
  reason?: string;
  requiredAuthorityLevel?: string;
}

/**
 * Valid state transitions mapping: Current Status -> Action -> Next Status
 */
const TRANSITION_MAP: Record<CaseWorkflowStatus, Partial<Record<WorkflowAction, CaseWorkflowStatus>>> = {
  NORMAL: {
    FLAG_FOR_INSPECTION: "FLAGGED",
  },
  FLAGGED: {
    ESCALATE_TO_STATE: "ESCALATED_STATE",
    ORDER_INQUIRY: "UNDER_INQUIRY",
    FREEZE_SANCTION: "SANCTION_FROZEN",
    RESOLVE_CASE: "RESOLVED",
    DISMISS_FLAG: "DISMISSED",
  },
  ESCALATED_DISTRICT: {
    ESCALATE_TO_STATE: "ESCALATED_STATE",
    ORDER_INQUIRY: "UNDER_INQUIRY",
    FREEZE_SANCTION: "SANCTION_FROZEN",
    RESOLVE_CASE: "RESOLVED",
    DISMISS_FLAG: "DISMISSED",
  },
  ESCALATED_STATE: {
    ESCALATE_TO_NATIONAL: "ESCALATED_NATIONAL",
    FREEZE_SANCTION: "SANCTION_FROZEN",
    ORDER_INQUIRY: "UNDER_INQUIRY",
    RESOLVE_CASE: "RESOLVED",
  },
  ESCALATED_NATIONAL: {
    FREEZE_SANCTION: "SANCTION_FROZEN",
    ORDER_INQUIRY: "UNDER_INQUIRY",
    RESOLVE_CASE: "RESOLVED",
  },
  SANCTION_FROZEN: {
    ORDER_INQUIRY: "UNDER_INQUIRY",
    RESOLVE_CASE: "RESOLVED",
  },
  UNDER_INQUIRY: {
    FREEZE_SANCTION: "SANCTION_FROZEN",
    RESOLVE_CASE: "RESOLVED",
    DISMISS_FLAG: "DISMISSED",
  },
  RESOLVED: {
    FLAG_FOR_INSPECTION: "FLAGGED", // Re-opened if new audit findings emerge
  },
  DISMISSED: {
    FLAG_FOR_INSPECTION: "FLAGGED",
  },
};

/**
 * Role-Based Action Entitlements
 */
const ROLE_PERMISSIONS: Record<AuthorityRole, WorkflowAction[]> = {
  DISTRICT_COLLECTOR: [
    "FLAG_FOR_INSPECTION",
    "ESCALATE_TO_STATE",
    "ORDER_INQUIRY",
    "FREEZE_SANCTION",
    "RESOLVE_CASE",
    "DISMISS_FLAG",
    "REQUEST_EXTENSION",
  ],
  STATE_NODAL_OFFICER: [
    "FLAG_FOR_INSPECTION",
    "ESCALATE_TO_NATIONAL",
    "ORDER_INQUIRY",
    "FREEZE_SANCTION",
    "RESOLVE_CASE",
    "DISMISS_FLAG",
  ],
  CENTRAL_OVERSIGHT: [
    "FLAG_FOR_INSPECTION",
    "ORDER_INQUIRY",
    "FREEZE_SANCTION",
    "RESOLVE_CASE",
    "DISMISS_FLAG",
  ],
  CAG_AUDITOR: [
    "FLAG_FOR_INSPECTION",
    "ORDER_INQUIRY",
    "FREEZE_SANCTION",
  ],
  ANTI_CORRUPTION_BUREAU: [
    "ORDER_INQUIRY",
    "FREEZE_SANCTION",
  ],
  IMPLEMENTING_AGENCY: [
    "SUBMIT_EXPLANATION",
    "REQUEST_EXTENSION",
  ],
  PUBLIC_CITIZEN: [],
};

export function canPerformAction(
  role: AuthorityRole,
  currentStatus: CaseWorkflowStatus,
  action: WorkflowAction
): StateTransitionResult {
  // Check if role is authorized
  const allowedActions = ROLE_PERMISSIONS[role] || [];
  if (!allowedActions.includes(action)) {
    return {
      allowed: false,
      reason: `Role '${role}' is not authorized to execute action '${action}'.`,
    };
  }

  // Check state machine transition
  const statusTransitions = TRANSITION_MAP[currentStatus];
  if (!statusTransitions || !statusTransitions[action]) {
    return {
      allowed: false,
      reason: `Action '${action}' is invalid from current state '${currentStatus}'.`,
    };
  }

  return {
    allowed: true,
    nextStatus: statusTransitions[action],
  };
}

export function evaluateAutoEscalation(
  riskScore: number,
  daysInCurrentState: number,
  currentStatus: CaseWorkflowStatus
): { shouldAutoEscalate: boolean; targetStatus?: CaseWorkflowStatus; reason?: string } {
  // Auto escalation rule: If high risk project lingers unresolved > 14 days at District level
  if (currentStatus === "FLAGGED" && riskScore >= 75.0 && daysInCurrentState >= 14) {
    return {
      shouldAutoEscalate: true,
      targetStatus: "ESCALATED_STATE",
      reason: `SLA Breach: High-risk project (Score ${riskScore.toFixed(1)}) remained unaddressed for ${daysInCurrentState} days. Auto-escalated to State Nodal Authority.`,
    };
  }

  // Auto escalation rule: If state level remains unaddressed > 21 days
  if (currentStatus === "ESCALATED_STATE" && riskScore >= 80.0 && daysInCurrentState >= 21) {
    return {
      shouldAutoEscalate: true,
      targetStatus: "ESCALATED_NATIONAL",
      reason: `SLA Breach: Critical anomaly project (Score ${riskScore.toFixed(1)}) exceeded 21-day State resolution SLA. Auto-escalated to MoSPI Central Oversight.`,
    };
  }

  return { shouldAutoEscalate: false };
}
