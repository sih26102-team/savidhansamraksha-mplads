"""
Multi-Tier Escalation Path Router & Case Assignment (Python)
Author: Poornesh (Case Management Lead)
"""

import time
from datetime import datetime, timedelta
from typing import Optional
from pydantic import BaseModel
from workflow_state_machine import CaseWorkflowStatus, WorkflowAction

class EscalationRecord(BaseModel):
    case_id: str
    work_id: str
    originating_tier: str
    target_tier: str
    reason: str
    initiated_by_user_id: str
    initiated_by_role: str
    created_at: str
    sla_deadline: str
    status: CaseWorkflowStatus
    action_required: str

def route_escalation(
    work_id: str,
    current_status: CaseWorkflowStatus,
    action: WorkflowAction,
    reason: str,
    user_id: str,
    user_role: str
) -> EscalationRecord:
    now = datetime.utcnow()
    case_id = f"CASE-{work_id}-{hex(int(time.time()))[2:].upper()}"

    target_tier = "STATE"
    originating_tier = "DISTRICT"
    target_status = CaseWorkflowStatus.ESCALATED_STATE
    sla_days = 7
    action_required = "Convene District Review Panel and submit verification report"

    if action == WorkflowAction.ESCALATE_TO_NATIONAL:
        originating_tier = "STATE"
        target_tier = "CENTRAL"
        target_status = CaseWorkflowStatus.ESCALATED_NATIONAL
        sla_days = 5
        action_required = "MoSPI Central Audit Directorate review and field inquiry"
    elif action == WorkflowAction.FREEZE_SANCTION:
        originating_tier = "STATE" if "STATE" in user_role else "DISTRICT"
        target_tier = "CENTRAL"
        target_status = CaseWorkflowStatus.SANCTION_FROZEN
        sla_days = 3
        action_required = "Treasury fund disbursement frozen pending financial inquiry"
    elif action == WorkflowAction.ORDER_INQUIRY:
        target_tier = "CAG_ACB"
        target_status = CaseWorkflowStatus.UNDER_INQUIRY
        sla_days = 14
        action_required = "Formal vigilance inquiry into physical vs expenditure divergence"

    sla_deadline = (now + timedelta(days=sla_days)).isoformat() + "Z"

    return EscalationRecord(
        case_id=case_id,
        work_id=work_id,
        originating_tier=originating_tier,
        target_tier=target_tier,
        reason=reason,
        initiated_by_user_id=user_id,
        initiated_by_role=user_role,
        created_at=now.isoformat() + "Z",
        sla_deadline=sla_deadline,
        status=target_status,
        action_required=action_required
    )
