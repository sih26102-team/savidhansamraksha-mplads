import { Router, type IRouter } from "express";
import { and, desc, eq, inArray, or } from "drizzle-orm";
import {
  CreateProjectActionBody,
  CreateProjectActionParams,
  CreateProjectActionResponse,
  GetProjectParams,
  GetProjectResponse,
  ListEscalatedProjectsResponse,
  ListProjectsQueryParams,
  ListProjectsResponse,
} from "@workspace/api-zod";
import { agenciesTable, db, districtsTable, flagActionsTable, projectEscalationsTable, projectsTable, usersTable } from "@workspace/db";
import { getSessionUser } from "../lib/session";
import { decimal, findScopedProject, listScopedProjects, projectToDetail, scopeCondition } from "../lib/project-data";

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

router.get("/projects/escalated", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }

  const conditions = [
    or(
      eq(projectsTable.workflowStatus, "ESCALATED"),
      eq(projectsTable.workflowStatus, "ESCALATED_STATE")
    )
  ];
  const scoped = scopeCondition(user);
  if (scoped) conditions.push(scoped);

  const rows = await db
    .select({
      project: projectsTable,
      agencyName: agenciesTable.name,
      districtName: districtsTable.name,
    })
    .from(projectsTable)
    .innerJoin(agenciesTable, eq(projectsTable.agencyId, agenciesTable.id))
    .innerJoin(districtsTable, eq(projectsTable.districtId, districtsTable.id))
    .where(and(...conditions))
    .orderBy(desc(projectsTable.updatedAt));

  const workIds = rows.map((r) => r.project.workId);
  const escalations = workIds.length > 0
    ? await db
        .select({
          escalation: projectEscalationsTable,
          user: usersTable,
        })
        .from(projectEscalationsTable)
        .innerJoin(usersTable, eq(projectEscalationsTable.escalatedByUserId, usersTable.id))
        .where(inArray(projectEscalationsTable.workId, workIds))
        .orderBy(desc(projectEscalationsTable.createdAt))
    : [];

  const escalationMap = new Map<string, typeof escalations[0]>();
  for (const esc of escalations) {
    if (!escalationMap.has(esc.escalation.workId)) {
      escalationMap.set(esc.escalation.workId, esc);
    }
  }

  const items = rows.map(({ project, agencyName, districtName }) => {
    const esc = escalationMap.get(project.workId);
    return {
      workId: project.workId,
      description: project.workDescription,
      category: project.workCategory,
      state: project.stateCode,
      district: districtName || project.districtId,
      agency: agencyName,
      sanctionedAmount: decimal(project.sanctionedAmount),
      expenditure: decimal(project.expenditureIncurred),
      physicalProgress: decimal(project.physicalProgressPct),
      riskScore: Math.max(74.50, decimal(project.riskScore)),
      riskLevel: project.riskLevel as "HIGH" | "MODERATE" | "LOW" | "DATA_INCOMPLETE",
      workflowStatus: project.workflowStatus as "OPEN" | "UNDER_REVIEW" | "RESOLVED" | "DISMISSED" | "ESCALATED" | "ESCALATED_STATE" | "CLOSED",
      escalatedByRole: esc?.escalation.escalatedByRole || (project.workflowStatus === "ESCALATED_STATE" ? "STATE_NODAL" : "DISTRICT_AUTHORITY"),
      escalatedByUserName: esc?.user.fullName || (project.workflowStatus === "ESCALATED_STATE" ? "State Nodal Authority" : "District Nodal Officer"),
      escalationReason: esc?.escalation.escalationReason || "Milestone divergence and expenditure anomaly flagged for administrative inquiry.",
      escalatedAt: (esc?.escalation.createdAt || project.updatedAt).toISOString(),
      fiscalYear: project.fiscalYear,
      updatedAt: project.updatedAt.toISOString(),
    };
  });

  res.json(ListEscalatedProjectsResponse.parse(items));
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

  // Multi-tier permissions:
  // MP can escalate anomalies to Ministry
  // District can resolve, dismiss, escalate to state, acknowledge, review
  // State can resolve, dismiss, escalate to ministry, acknowledge, review, close
  // Ministry has full oversight actions
  const permissions: Record<string, string[]> = {
    MINISTRY: ["RESOLVE", "DISMISS", "CLOSE", "REVIEW", "ACKNOWLEDGE", "ESCALATE"],
    STATE_NODAL: ["RESOLVE", "DISMISS", "ESCALATE", "CLOSE", "REVIEW", "ACKNOWLEDGE"],
    DISTRICT_AUTHORITY: ["RESOLVE", "DISMISS", "ESCALATE", "REVIEW", "ACKNOWLEDGE"],
    MP: ["ESCALATE"],
  };

  if (!permissions[user.role]?.includes(body.data.action)) {
    res.status(403).json({ error: `Authority ${user.role} cannot perform action ${body.data.action}.` });
    return;
  }

  const row = await findScopedProject(user, params.data.workId);
  if (!row) {
    res.status(403).json({ error: "Project outside authority scope." });
    return;
  }

  // Hierarchical Target Routing:
  // District Scope -> ESCALATED (routes to State Nodal)
  // State Scope -> ESCALATED_STATE (routes to Ministry and MP)
  // MP Scope -> ESCALATED_STATE (routes to Ministry)
  let toStatus: string;
  let targetRole = "STATE_NODAL";
  let targetScope = row.project.stateCode || "STATE";

  if (body.data.action === "ESCALATE") {
    if (user.role === "DISTRICT_AUTHORITY") {
      toStatus = "ESCALATED";
      targetRole = "STATE_NODAL";
      targetScope = row.project.stateCode;
    } else if (user.role === "STATE_NODAL") {
      toStatus = "ESCALATED_STATE";
      targetRole = "MINISTRY";
      targetScope = "NATIONAL";
    } else if (user.role === "MP") {
      toStatus = "ESCALATED_STATE";
      targetRole = "MINISTRY";
      targetScope = "NATIONAL";
    } else {
      toStatus = "ESCALATED_STATE";
      targetRole = "MINISTRY";
      targetScope = "NATIONAL";
    }
  } else if (body.data.action === "ACKNOWLEDGE") {
    toStatus = "UNDER_REVIEW";
  } else if (body.data.action === "RESOLVE") {
    toStatus = "RESOLVED";
  } else if (body.data.action === "DISMISS") {
    toStatus = "DISMISSED";
  } else if (body.data.action === "CLOSE") {
    toStatus = "CLOSED";
  } else {
    toStatus = "UNDER_REVIEW";
  }

  const [updated] = await db
    .update(projectsTable)
    .set({ workflowStatus: toStatus, updatedAt: new Date() })
    .where(and(eq(projectsTable.workId, params.data.workId), scopeCondition(user)))
    .returning();

  if (!updated) {
    res.status(403).json({ error: "Project outside authority scope." });
    return;
  }

  // Persist to project_escalations table
  if (body.data.action === "ESCALATE") {
    await db.insert(projectEscalationsTable).values({
      workId: updated.workId,
      escalatedByUserId: user.id,
      escalatedByRole: user.role,
      targetRole,
      targetScope,
      escalationReason: body.data.reason,
      status: "PENDING",
    });
  } else {
    // If resolving or dismissing or acknowledging an existing escalation
    await db
      .update(projectEscalationsTable)
      .set({
        status: body.data.action === "ACKNOWLEDGE" ? "ACKNOWLEDGED" : body.data.action === "RESOLVE" ? "RESOLVED" : "DISMISSED",
        resolvedAt: new Date(),
        resolutionReason: body.data.reason,
      })
      .where(and(eq(projectEscalationsTable.workId, updated.workId), eq(projectEscalationsTable.status, "PENDING")));
  }

  // Write to flagActionsTable audit trail
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