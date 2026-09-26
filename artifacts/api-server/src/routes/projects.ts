import { Router, type IRouter } from "express";
import { and, eq } from "drizzle-orm";
import { CreateProjectActionBody, CreateProjectActionParams, CreateProjectActionResponse, GetProjectParams, GetProjectResponse, ListProjectsQueryParams, ListProjectsResponse } from "@workspace/api-zod";
import { db, flagActionsTable, projectsTable } from "@workspace/db";
import { getSessionUser } from "../lib/session";
import { findScopedProject, listScopedProjects, projectToDetail, scopeCondition } from "../lib/project-data";

const router: IRouter = Router();

router.get("/projects", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const parsed = ListProjectsQueryParams.safeParse(req.query);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const result = await listScopedProjects(user, parsed.data);
  res.json(ListProjectsResponse.parse(result));
});

router.get("/projects/:workId", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const params = GetProjectParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  const row = await findScopedProject(user, params.data.workId);
  if (!row) {
    const [exists] = await db.select({ workId: projectsTable.workId }).from(projectsTable).where(eq(projectsTable.workId, params.data.workId));
    res.status(exists ? 403 : 404).json({ error: exists ? "Project outside authority scope" : "Project not found" });
    return;
  }
  res.json(GetProjectResponse.parse(projectToDetail(row)));
});

router.post("/projects/:workId/actions", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const params = CreateProjectActionParams.safeParse(req.params);
  const body = CreateProjectActionBody.safeParse(req.body);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  if (!body.success) {
    res.status(400).json({ error: body.error.message });
    return;
  }
  if (user.readOnly || user.role === "MP") {
    res.status(403).json({ error: "MP accounts are read-only and cannot perform workflow actions." });
    return;
  }
  const permissions: Record<string, string[]> = {
    MINISTRY: ["RESOLVE", "DISMISS", "CLOSE", "REVIEW"],
    STATE_NODAL: ["RESOLVE", "DISMISS", "ESCALATE", "CLOSE", "REVIEW"],
    DISTRICT_AUTHORITY: ["RESOLVE", "DISMISS", "ESCALATE", "REVIEW"],
  };
  if (!permissions[user.role]?.includes(body.data.action)) {
    res.status(403).json({ error: "This authority cannot perform the requested action." });
    return;
  }
  const row = await findScopedProject(user, params.data.workId);
  if (!row) {
    res.status(403).json({ error: "Project outside authority scope." });
    return;
  }
  const nextStatus: Record<string, string> = { RESOLVE: "RESOLVED", DISMISS: "DISMISSED", ESCALATE: "ESCALATED", CLOSE: "CLOSED", REVIEW: "UNDER_REVIEW" };
  const toStatus = nextStatus[body.data.action];
  const [updated] = await db.update(projectsTable).set({ workflowStatus: toStatus, updatedAt: new Date() }).where(and(eq(projectsTable.workId, params.data.workId), scopeCondition(user))).returning();
  if (!updated) {
    res.status(403).json({ error: "Project outside authority scope." });
    return;
  }
  const [audit] = await db.insert(flagActionsTable).values({
    workId: updated.workId,
    userId: user.id,
    role: user.role,
    action: body.data.action,
    reason: body.data.reason,
    fromStatus: row.project.workflowStatus,
    toStatus,
  }).returning();
  res.json(CreateProjectActionResponse.parse({
    workId: updated.workId,
    workflowStatus: updated.workflowStatus,
    audit: {
      id: String(audit.id),
      workId: audit.workId,
      userName: user.fullName,
      role: audit.role,
      action: audit.action,
      timestamp: audit.timestamp.toISOString(),
      reason: audit.reason,
      fromStatus: audit.fromStatus,
      toStatus: audit.toStatus,
    },
  }));
});

export default router;