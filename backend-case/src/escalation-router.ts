/**
 * Multi-Tier Escalation Path Router & Case Assignment
 * Author: Poornesh (Case Management Lead)
 */

import { CaseWorkflowStatus, WorkflowAction } from "./workflow-state-machine.js";

export interface EscalationRecord {
  caseId: string;
  workId: string;
  originatingTier: "DISTRICT" | "STATE" | "CENTRAL";
  targetTier: "STATE" | "CENTRAL" | "CAG_ACB";
  reason: string;
  initiatedByUserId: string;
  initiatedByRole: string;
  createdAt: string;
  slaDeadline: string;
  status: CaseWorkflowStatus;
  actionRequired: string;
}

export function routeEscalation(
  workId: string,
  currentStatus: CaseWorkflowStatus,
  action: WorkflowAction,
  reason: string,
  userId: string,
  userRole: string
): EscalationRecord {
  const now = new Date();
  const caseId = `CASE-${workId}-${Date.now().toString(36).toUpperCase()}`;

  let targetTier: EscalationRecord["targetTier"] = "STATE";
  let originatingTier: EscalationRecord["originatingTier"] = "DISTRICT";
  let targetStatus: CaseWorkflowStatus = "ESCALATED_STATE";
  let slaDays = 7;
  let actionRequired = "Convene District Review Panel and submit verification report";

  if (action === "ESCALATE_TO_NATIONAL") {
    originatingTier = "STATE";
    targetTier = "CENTRAL";
    targetStatus = "ESCALATED_NATIONAL";
    slaDays = 5;
    actionRequired = "MoSPI Central Audit Directorate review and field inquiry";
  } else if (action === "FREEZE_SANCTION") {
    originatingTier = userRole.includes("STATE") ? "STATE" : "DISTRICT";
    targetTier = "CENTRAL";
    targetStatus = "SANCTION_FROZEN";
    slaDays = 3;
    actionRequired = "Treasury fund disbursement frozen pending financial inquiry";
  } else if (action === "ORDER_INQUIRY") {
    targetTier = "CAG_ACB";
    targetStatus = "UNDER_INQUIRY";
    slaDays = 14;
    actionRequired = "Formal vigilance inquiry into physical vs expenditure divergence";
  }

  const slaDeadline = new Date(now.getTime() + slaDays * 24 * 60 * 60 * 1000).toISOString();

  return {
    caseId,
    workId,
    originatingTier,
    targetTier,
    reason,
    initiatedByUserId: userId,
    initiatedByRole: userRole,
    createdAt: now.toISOString(),
    slaDeadline,
    status: targetStatus,
    actionRequired,
  };
}
