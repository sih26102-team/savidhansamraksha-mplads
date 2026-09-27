/**
 * Case Notification & SLA Alert Dispatcher
 * Author: Poornesh (Case Management Lead)
 */

export interface CaseNotification {
  notificationId: string;
  recipientRole: string;
  priority: "CRITICAL" | "HIGH" | "MEDIUM" | "ROUTINE";
  title: string;
  message: string;
  workId: string;
  caseId?: string;
  sentAt: string;
}

export function dispatchCaseNotification(
  priority: CaseNotification["priority"],
  recipientRole: string,
  workId: string,
  title: string,
  message: string,
  caseId?: string
): CaseNotification {
  const notificationId = `NOTIF-${Date.now().toString(36)}-${Math.random().toString(36).substring(2, 6)}`;
  const notification: CaseNotification = {
    notificationId,
    recipientRole,
    priority,
    title,
    message,
    workId,
    caseId,
    sentAt: new Date().toISOString(),
  };

  // In production, this pushes to WebSocket bus, SMS gateway (NIC SMS), or email service
  console.log(`[Notification Dispatcher] [${priority}] -> ${recipientRole}: ${title} (${workId})`);
  return notification;
}
