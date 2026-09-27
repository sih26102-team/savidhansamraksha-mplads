"""
Hierarchical Workflow State Machine & Role Permission Matrix
Author: Poornesh (Case Management Lead)
"""

from enum import Enum
from typing import Dict, List, Optional, Set, Any
from pydantic import BaseModel

class AuthorityRole(str, Enum):
    DISTRICT_COLLECTOR = "DISTRICT_COLLECTOR"
    STATE_NODAL_OFFICER = "STATE_NODAL_OFFICER"
    CENTRAL_OVERSIGHT = "CENTRAL_OVERSIGHT"
    CAG_AUDITOR = "CAG_AUDITOR"
    ANTI_CORRUPTION_BUREAU = "ANTI_CORRUPTION_BUREAU"
    IMPLEMENTING_AGENCY = "IMPLEMENTING_AGENCY"
    PUBLIC_CITIZEN = "PUBLIC_CITIZEN"

class CaseWorkflowStatus(str, Enum):
    NORMAL = "NORMAL"
    FLAGGED = "FLAGGED"
    ESCALATED_DISTRICT = "ESCALATED_DISTRICT"
    ESCALATED_STATE = "ESCALATED_STATE"
    ESCALATED_NATIONAL = "ESCALATED_NATIONAL"
    SANCTION_FROZEN = "SANCTION_FROZEN"
    UNDER_INQUIRY = "UNDER_INQUIRY"
    RESOLVED = "RESOLVED"
    DISMISSED = "DISMISSED"

class WorkflowAction(str, Enum):
    FLAG_FOR_INSPECTION = "FLAG_FOR_INSPECTION"
    ESCALATE_TO_STATE = "ESCALATE_TO_STATE"
    ESCALATE_TO_NATIONAL = "ESCALATE_TO_NATIONAL"
    FREEZE_SANCTION = "FREEZE_SANCTION"
    ORDER_INQUIRY = "ORDER_INQUIRY"
    RESOLVE_CASE = "RESOLVE_CASE"
    DISMISS_FLAG = "DISMISS_FLAG"
    SUBMIT_EXPLANATION = "SUBMIT_EXPLANATION"
    REQUEST_EXTENSION = "REQUEST_EXTENSION"

class StateTransitionResult(BaseModel):
    allowed: bool
    next_status: Optional[CaseWorkflowStatus] = None
    reason: Optional[str] = None

# Valid State Transitions
TRANSITION_MAP: Dict[CaseWorkflowStatus, Dict[WorkflowAction, CaseWorkflowStatus]] = {
    CaseWorkflowStatus.NORMAL: {
        WorkflowAction.FLAG_FOR_INSPECTION: CaseWorkflowStatus.FLAGGED,
    },
    CaseWorkflowStatus.FLAGGED: {
        WorkflowAction.ESCALATE_TO_STATE: CaseWorkflowStatus.ESCALATED_STATE,
        WorkflowAction.ORDER_INQUIRY: CaseWorkflowStatus.UNDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION: CaseWorkflowStatus.SANCTION_FROZEN,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
        WorkflowAction.DISMISS_FLAG: CaseWorkflowStatus.DISMISSED,
    },
    CaseWorkflowStatus.ESCALATED_DISTRICT: {
        WorkflowAction.ESCALATE_TO_STATE: CaseWorkflowStatus.ESCALATED_STATE,
        WorkflowAction.ORDER_INQUIRY: CaseWorkflowStatus.UNDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION: CaseWorkflowStatus.SANCTION_FROZEN,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
        WorkflowAction.DISMISS_FLAG: CaseWorkflowStatus.DISMISSED,
    },
    CaseWorkflowStatus.ESCALATED_STATE: {
        WorkflowAction.ESCALATE_TO_NATIONAL: CaseWorkflowStatus.ESCALATED_NATIONAL,
        WorkflowAction.FREEZE_SANCTION: CaseWorkflowStatus.SANCTION_FROZEN,
        WorkflowAction.ORDER_INQUIRY: CaseWorkflowStatus.UNDER_INQUIRY,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
    },
    CaseWorkflowStatus.ESCALATED_NATIONAL: {
        WorkflowAction.FREEZE_SANCTION: CaseWorkflowStatus.SANCTION_FROZEN,
        WorkflowAction.ORDER_INQUIRY: CaseWorkflowStatus.UNDER_INQUIRY,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
    },
    CaseWorkflowStatus.SANCTION_FROZEN: {
        WorkflowAction.ORDER_INQUIRY: CaseWorkflowStatus.UNDER_INQUIRY,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
    },
    CaseWorkflowStatus.UNDER_INQUIRY: {
        WorkflowAction.FREEZE_SANCTION: CaseWorkflowStatus.SANCTION_FROZEN,
        WorkflowAction.RESOLVE_CASE: CaseWorkflowStatus.RESOLVED,
        WorkflowAction.DISMISS_FLAG: CaseWorkflowStatus.DISMISSED,
    },
    CaseWorkflowStatus.RESOLVED: {
        WorkflowAction.FLAG_FOR_INSPECTION: CaseWorkflowStatus.FLAGGED,
    },
    CaseWorkflowStatus.DISMISSED: {
        WorkflowAction.FLAG_FOR_INSPECTION: CaseWorkflowStatus.FLAGGED,
    },
}

# Role Permissions
ROLE_PERMISSIONS: Dict[AuthorityRole, Set[WorkflowAction]] = {
    AuthorityRole.DISTRICT_COLLECTOR: {
        WorkflowAction.FLAG_FOR_INSPECTION,
        WorkflowAction.ESCALATE_TO_STATE,
        WorkflowAction.ORDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION,
        WorkflowAction.RESOLVE_CASE,
        WorkflowAction.DISMISS_FLAG,
        WorkflowAction.REQUEST_EXTENSION,
    },
    AuthorityRole.STATE_NODAL_OFFICER: {
        WorkflowAction.FLAG_FOR_INSPECTION,
        WorkflowAction.ESCALATE_TO_NATIONAL,
        WorkflowAction.ORDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION,
        WorkflowAction.RESOLVE_CASE,
        WorkflowAction.DISMISS_FLAG,
    },
    AuthorityRole.CENTRAL_OVERSIGHT: {
        WorkflowAction.FLAG_FOR_INSPECTION,
        WorkflowAction.ORDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION,
        WorkflowAction.RESOLVE_CASE,
        WorkflowAction.DISMISS_FLAG,
    },
    AuthorityRole.CAG_AUDITOR: {
        WorkflowAction.FLAG_FOR_INSPECTION,
        WorkflowAction.ORDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION,
    },
    AuthorityRole.ANTI_CORRUPTION_BUREAU: {
        WorkflowAction.ORDER_INQUIRY,
        WorkflowAction.FREEZE_SANCTION,
    },
    AuthorityRole.IMPLEMENTING_AGENCY: {
        WorkflowAction.SUBMIT_EXPLANATION,
        WorkflowAction.REQUEST_EXTENSION,
    },
    AuthorityRole.PUBLIC_CITIZEN: set(),
}

def can_perform_action(
    role: AuthorityRole,
    current_status: CaseWorkflowStatus,
    action: WorkflowAction
) -> StateTransitionResult:
    allowed_actions = ROLE_PERMISSIONS.get(role, set())
    if action not in allowed_actions:
        return StateTransitionResult(
            allowed=False,
            reason=f"Role '{role.value}' is not authorized to execute action '{action.value}'."
        )

    status_transitions = TRANSITION_MAP.get(current_status, {})
    next_status = status_transitions.get(action)
    if not next_status:
        return StateTransitionResult(
            allowed=False,
            reason=f"Action '{action.value}' is invalid from current state '{current_status.value}'."
        )

    return StateTransitionResult(
        allowed=True,
        next_status=next_status
    )

def evaluate_auto_escalation(
    risk_score: float,
    days_in_state: int,
    current_status: CaseWorkflowStatus
) -> Dict[str, Any]:
    if current_status == CaseWorkflowStatus.FLAGGED and risk_score >= 75.0 and days_in_state >= 14:
        return {
            "should_auto_escalate": True,
            "target_status": CaseWorkflowStatus.ESCALATED_STATE,
            "reason": f"SLA Breach: High-risk project (Score {risk_score:.1f}) remained unaddressed for {days_in_state} days. Auto-escalated to State Nodal Authority."
        }
    if current_status == CaseWorkflowStatus.ESCALATED_STATE and risk_score >= 80.0 and days_in_state >= 21:
        return {
            "should_auto_escalate": True,
            "target_status": CaseWorkflowStatus.ESCALATED_NATIONAL,
            "reason": f"SLA Breach: Critical anomaly project (Score {risk_score:.1f}) exceeded 21-day State resolution SLA. Auto-escalated to MoSPI Central Oversight."
        }
    return {"should_auto_escalate": False}
