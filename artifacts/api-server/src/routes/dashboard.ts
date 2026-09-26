import { Router, type IRouter } from "express";
import { GetDashboardSummaryResponse } from "@workspace/api-zod";
import { getSessionUser } from "../lib/session";
import { listScopedProjects } from "../lib/project-data";
import { db, flagActionsTable, projectsTable, usersTable } from "@workspace/db";
import { and, desc, eq } from "drizzle-orm";

const router: IRouter = Router();

router.get("/dashboard/summary", async (req, res): Promise<void> => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  const result = await listScopedProjects(user, { limit: 10000, offset: 0 });
  const totals = result.items.reduce((summary, item) => {
    summary.totalProjects += 1;
    summary.sanctionedAmount += item.sanctionedAmount;
    summary.expenditure += item.expenditure;
    summary.averageProgress += item.physicalProgress;
    if (item.riskLevel === "HIGH") summary.highRisk += 1;
    if (item.riskLevel === "MODERATE") summary.moderateRisk += 1;
    if (item.riskLevel === "LOW") summary.lowRisk += 1;
    if (item.riskLevel === "DATA_INCOMPLETE") summary.dataIncomplete += 1;
    return summary;
  }, { totalProjects: 0, sanctionedAmount: 0, expenditure: 0, averageProgress: 0, highRisk: 0, moderateRisk: 0, lowRisk: 0, dataIncomplete: 0 });
  totals.averageProgress = totals.totalProjects ? Math.round((totals.averageProgress / totals.totalProjects) * 10) / 10 : 0;
  const byRisk = ["HIGH", "MODERATE", "LOW", "DATA_INCOMPLETE"].map((label) => ({ label, value: result.items.filter((item) => item.riskLevel === label).length }));
  const statusLabels = ["OPEN", "UNDER_REVIEW", "ESCALATED", "RESOLVED", "DISMISSED", "CLOSED"];
  const statusDistribution = statusLabels.map((label) => ({ label, value: result.items.filter((item) => item.workflowStatus === label).length }));
  const categoryDistribution = Array.from(new Set(result.items.map((item) => item.category))).map((label) => ({ label, value: result.items.filter((item) => item.category === label).length })).sort((a, b) => b.value - a.value).slice(0, 8);
  const fiscalTrend = Array.from(new Set(result.items.map((item) => item.fiscalYear))).sort().map((label) => {
    const items = result.items.filter((item) => item.fiscalYear === label);
    return { label, projects: items.length, expenditure: items.reduce((sum, item) => sum + item.expenditure, 0) };
  });
  const auditConditions = user.role === "MINISTRY" ? undefined : user.role === "STATE_NODAL" && user.stateCode ? eq(projectsTable.stateCode, user.stateCode) : user.role === "DISTRICT_AUTHORITY" && user.districtId ? eq(projectsTable.districtId, user.districtId) : user.constituencyId ? eq(projectsTable.constituencyId, user.constituencyId) : and(eq(projectsTable.workId, "__no_scope__"));
  const recentRows = await db.select({ action: flagActionsTable, user: usersTable }).from(flagActionsTable).innerJoin(usersTable, eq(flagActionsTable.userId, usersTable.id)).innerJoin(projectsTable, eq(flagActionsTable.workId, projectsTable.workId)).where(auditConditions).orderBy(desc(flagActionsTable.timestamp)).limit(6);
  const recentActivity = recentRows.map(({ action, user: actor }) => ({ id: String(action.id), workId: action.workId, userName: actor.fullName, role: action.role, action: action.action, timestamp: action.timestamp.toISOString(), reason: action.reason, fromStatus: action.fromStatus, toStatus: action.toStatus }));
  res.json(GetDashboardSummaryResponse.parse({
    scopeLabel: user.scopeLabel,
    syntheticLabel: "Synthetic Demonstration Dataset",
    totals,
    riskDistribution: byRisk,
    statusDistribution,
    categoryDistribution,
    fiscalTrend,
    recentActivity,
  }));
});

export default router;