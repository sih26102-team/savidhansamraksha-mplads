/**
 * Tamper-Evident Action Audit Logger
 * Author: Poornesh (Case Management Lead)
 */

import { createHash } from "node:crypto";

export interface CaseAuditEntry {
  entryId: string;
  workId: string;
  action: string;
  previousStatus: string;
  newStatus: string;
  performedByUserId: string;
  performedByRole: string;
  notes: string;
  timestamp: string;
  previousHash: string;
  currentHash: string;
}

export function generateAuditHash(
  previousHash: string,
  workId: string,
  action: string,
  timestamp: string,
  userId: string,
  notes: string
): string {
  const payload = `${previousHash}|${workId}|${action}|${timestamp}|${userId}|${notes}`;
  return createHash("sha256").update(payload).digest("hex");
}

export function createAuditLogEntry(
  workId: string,
  action: string,
  previousStatus: string,
  newStatus: string,
  userId: string,
  userRole: string,
  notes: string,
  previousHash = "0000000000000000000000000000000000000000000000000000000000000000"
): CaseAuditEntry {
  const timestamp = new Date().toISOString();
  const currentHash = generateAuditHash(previousHash, workId, action, timestamp, userId, notes);
  const entryId = `AUDIT-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 6)}`;

  return {
    entryId,
    workId,
    action,
    previousStatus,
    newStatus,
    performedByUserId: userId,
    performedByRole: userRole,
    notes,
    timestamp,
    previousHash,
    currentHash,
  };
}

export function verifyAuditChain(entries: CaseAuditEntry[]): boolean {
  for (let i = 1; i < entries.length; i++) {
    const prev = entries[i - 1];
    const curr = entries[i];
    if (curr.previousHash !== prev.currentHash) {
      return false;
    }
    const computed = generateAuditHash(
      curr.previousHash,
      curr.workId,
      curr.action,
      curr.timestamp,
      curr.performedByUserId,
      curr.notes
    );
    if (computed !== curr.currentHash) {
      return false;
    }
  }
  return true;
}
