"""
Tamper-Evident Action Audit Logger (Python)
Author: Poornesh (Case Management Lead)
"""

import hashlib
import time
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel

class CaseAuditEntry(BaseModel):
    entry_id: str
    work_id: str
    action: str
    previous_status: str
    new_status: str
    performed_by_user_id: str
    performed_by_role: str
    notes: str
    timestamp: str
    previous_hash: str
    current_hash: str

def generate_audit_hash(
    previous_hash: str,
    work_id: str,
    action: str,
    timestamp: str,
    user_id: str,
    notes: str
) -> str:
    payload = f"{previous_hash}|{work_id}|{action}|{timestamp}|{user_id}|{notes}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

def create_audit_log_entry(
    work_id: str,
    action: str,
    previous_status: str,
    new_status: str,
    user_id: str,
    user_role: str,
    notes: str,
    previous_hash: str = "0" * 64
) -> CaseAuditEntry:
    timestamp = datetime.utcnow().isoformat() + "Z"
    current_hash = generate_audit_hash(previous_hash, work_id, action, timestamp, user_id, notes)
    entry_id = f"AUDIT-{hex(int(time.time()))[2:].upper()}-{work_id[:6]}"

    return CaseAuditEntry(
        entry_id=entry_id,
        work_id=work_id,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        performed_by_user_id=user_id,
        performed_by_role=user_role,
        notes=notes,
        timestamp=timestamp,
        previous_hash=previous_hash,
        current_hash=current_hash
    )

def verify_audit_chain(entries: List[CaseAuditEntry]) -> bool:
    for i in range(1, len(entries)):
        prev = entries[i - 1]
        curr = entries[i]
        if curr.previous_hash != prev.current_hash:
            return False
        computed = generate_audit_hash(
            curr.previous_hash,
            curr.work_id,
            curr.action,
            curr.timestamp,
            curr.performed_by_user_id,
            curr.notes
        )
        if computed != curr.current_hash:
            return False
    return True
