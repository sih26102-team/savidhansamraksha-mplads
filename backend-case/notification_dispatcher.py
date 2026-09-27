"""
Case Notification & SLA Alert Dispatcher (Python)
Author: Poornesh (Case Management Lead)
"""

import time
from datetime import datetime
from typing import Optional
from pydantic import BaseModel

class CaseNotification(BaseModel):
    notification_id: str
    recipient_role: str
    priority: str
    title: str
    message: str
    work_id: str
    case_id: Optional[str] = None
    sent_at: str

def dispatch_case_notification(
    priority: str,
    recipient_role: str,
    work_id: str,
    title: str,
    message: str,
    case_id: Optional[str] = None
) -> CaseNotification:
    notification_id = f"NOTIF-{hex(int(time.time()))[2:].upper()}-{work_id[:6]}"
    notif = CaseNotification(
        notification_id=notification_id,
        recipient_role=recipient_role,
        priority=priority,
        title=title,
        message=message,
        work_id=work_id,
        case_id=case_id,
        sent_at=datetime.utcnow().isoformat() + "Z"
    )
    print(f"[Notification] [{priority}] -> {recipient_role}: {title} ({work_id})")
    return notif
