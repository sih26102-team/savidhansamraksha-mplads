import { Router, type IRouter } from "express";
import { desc, eq } from "drizzle-orm";
import { ListProjectAuditParams, ListProjectAuditResponse, ListRecentAuditResponse } from "@workspace/api-zod";
import { db, flagActionsTable, projectsTable, usersTable } from "@workspace/db";
import { getSessionUser } from "../lib/session";
import { findScopedProject } from "../lib/project-data";

const router: IRouter = Router();
const mapAudit = (entry: typeof flagActionsTable.$inferSelect, userName: string) => ({
  id: String(entry.id),
  workId: entry.workId,
  userName,
  role: entry.role,
  action: entry.action,
  timestamp: entry.timestamp.toISOString(),
  reason: entry.reason,
  fromStatus: entry.fromStatus,
  toStatus: entry.toStatus,
});

router.get("/projects/:workId/audit", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const params = ListProjectAuditParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  const project = await findScopedProject(user, params.data.workId);
  if (!project) {
    res.status(403).json({ error: "Project outside authority scope." });
    return;
  }
  const rows = await db.select({ action: flagActionsTable, user: usersTable }).from(flagActionsTable).innerJoin(usersTable, eq(flagActionsTable.userId, usersTable.id)).where(eq(flagActionsTable.workId, params.data.workId)).orderBy(desc(flagActionsTable.timestamp));
  res.json(ListProjectAuditResponse.parse(rows.map(({ action, user: actor }) => mapAudit(action, actor.fullName))));
});

router.get("/audit/recent", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const rows = await db.select({ action: flagActionsTable, user: usersTable }).from(flagActionsTable).innerJoin(usersTable, eq(flagActionsTable.userId, usersTable.id)).innerJoin(projectsTable, eq(flagActionsTable.workId, projectsTable.workId)).orderBy(desc(flagActionsTable.timestamp)).limit(12);
  res.json(ListRecentAuditResponse.parse(rows.map(({ action, user: actor }) => mapAudit(action, actor.fullName))));
});

export default router;