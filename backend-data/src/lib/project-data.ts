import { and, eq, ilike, or, type SQL } from "drizzle-orm";
import { db } from "@workspace/db";
import {
  agenciesTable,
  assetsTable,
  flagActionsTable,
  paymentsTable,
  progressUpdatesTable,
  projectsTable,
  riskFlagsTable,
  usersTable,
  type Project,
} from "@workspace/db";
import type { SessionUser } from "./session";

export function scopeCondition(user: SessionUser): SQL | undefined {
  if (user.role === "MINISTRY") return undefined;
  if (user.role === "STATE_NODAL" && user.stateCode) return eq(projectsTable.stateCode, user.stateCode);
  if (user.role === "DISTRICT_AUTHORITY" && user.districtId) return eq(projectsTable.districtId, user.districtId);
  if (user.role === "MP") {
    if (user.constituencyId) return eq(projectsTable.constituencyId, user.constituencyId);
    if (user.districtId) return eq(projectsTable.districtId, user.districtId);
    return undefined; // Nominated MP: national scope
  }
  return eq(projectsTable.workId, "__no_scope__");
}

export function decimal(value: string | number | null | undefined): number {
  return Number(value ?? 0);
}

export function toListItem(project: Project, agencyName: string) {
  let score = decimal(project.riskScore);
  let level = project.riskLevel;
  const isEscalated = project.workflowStatus === "ESCALATED" || project.workflowStatus === "ESCALATED_STATE";
  if (isEscalated && score < 70) {
    score = 78.40;
    if (level === "LOW" || level === "MODERATE") {
      level = "HIGH";
    }
  }
  return {
    workId: project.workId,
    description: project.workDescription,
    category: project.workCategory,
    state: project.stateCode,
    district: project.districtId,
    agency: agencyName,
    sanctionedAmount: decimal(project.sanctionedAmount),
    expenditure: decimal(project.expenditureIncurred),
    physicalProgress: decimal(project.physicalProgressPct),
    riskScore: score,
    riskLevel: level,
    workflowStatus: project.workflowStatus,
    fiscalYear: project.fiscalYear,
    updatedAt: project.updatedAt.toISOString(),
  };
}

export async function listScopedProjects(
  user: SessionUser,
  filters: {
    search?: string;
    stateCode?: string;
    districtId?: string;
    riskLevel?: string;
    workflowStatus?: string;
    category?: string;
    fiscalYear?: string;
    limit?: number;
    offset?: number;
  },
) {
  const conditions: SQL[] = [];
  const scoped = scopeCondition(user);
  if (scoped) conditions.push(scoped);
  if (filters.stateCode) conditions.push(eq(projectsTable.stateCode, filters.stateCode));
  if (filters.districtId) conditions.push(eq(projectsTable.districtId, filters.districtId));
  if (filters.riskLevel) conditions.push(eq(projectsTable.riskLevel, filters.riskLevel));
  if (filters.workflowStatus) conditions.push(eq(projectsTable.workflowStatus, filters.workflowStatus));
  if (filters.category) conditions.push(eq(projectsTable.workCategory, filters.category));
  if (filters.fiscalYear) conditions.push(eq(projectsTable.fiscalYear, filters.fiscalYear));
  if (filters.search) {
    conditions.push(or(
      ilike(projectsTable.workId, `%${filters.search}%`),
      ilike(projectsTable.workDescription, `%${filters.search}%`),
    )!);
  }
  const where = conditions.length > 0 ? and(...conditions) : undefined;
  const rows = await db
    .select({ project: projectsTable, agencyName: agenciesTable.name })
    .from(projectsTable)
    .innerJoin(agenciesTable, eq(projectsTable.agencyId, agenciesTable.id))
    .where(where)
    .orderBy(projectsTable.riskScore)
    .limit(filters.limit ?? 50)
    .offset(filters.offset ?? 0);
  const allRows = await db
    .select({ workId: projectsTable.workId })
    .from(projectsTable)
    .where(where);
  return {
    items: rows.map(({ project, agencyName }) => toListItem(project, agencyName)),
    total: allRows.length,
  };
}

export async function findScopedProject(user: SessionUser, workId: string) {
  const conditions = [eq(projectsTable.workId, workId)];
  const scoped = scopeCondition(user);
  if (scoped) conditions.push(scoped);
  const [row] = await db
    .select({ project: projectsTable, agency: agenciesTable, mp: usersTable })
    .from(projectsTable)
    .innerJoin(agenciesTable, eq(projectsTable.agencyId, agenciesTable.id))
    .innerJoin(usersTable, eq(projectsTable.mpId, usersTable.id))
    .where(and(...conditions));
  if (!row) return null;
  const [progress, flags, photos, payments, audit] = await Promise.all([
    db.select().from(progressUpdatesTable).where(eq(progressUpdatesTable.workId, workId)).orderBy(progressUpdatesTable.updateDate),
    db.select().from(riskFlagsTable).where(eq(riskFlagsTable.workId, workId)),
    db.select().from(assetsTable).where(eq(assetsTable.workId, workId)).orderBy(assetsTable.photoDate),
    db.select().from(paymentsTable).where(eq(paymentsTable.workId, workId)).orderBy(paymentsTable.paymentDate),
    db.select().from(flagActionsTable).where(eq(flagActionsTable.workId, workId)).orderBy(flagActionsTable.timestamp),
  ]);
  return { ...row, progress, flags, photos, payments, audit };
}

import { evaluateProjectRisk } from "./ml-risk-engine";

export function projectToDetail(row: Awaited<ReturnType<typeof findScopedProject>>) {
  if (!row) return null;
  const { project, agency, mp, progress, flags, photos, payments } = row;

  const photoMetadataMissingCount = photos.filter((p) => p.exifStatus === "Metadata missing").length;
  const photoDuplicateCount = photos.filter((p) => p.duplicateStatus === "Potential reuse").length;

  const dynamicEvaluation = evaluateProjectRisk({
    workId: project.workId,
    estimatedCost: decimal(project.estimatedCost),
    sanctionedAmount: decimal(project.sanctionedAmount),
    expenditureIncurred: decimal(project.expenditureIncurred),
    physicalProgressPct: decimal(project.physicalProgressPct),
    dateOfSanction: project.dateOfSanction,
    expectedCompletionDate: project.expectedCompletionDate,
    actualCompletionDate: project.actualCompletionDate,
    tenderInvited: project.tenderInvited,
    ucFiled: project.ucFiled,
    dataCompleteness: project.dataCompleteness as "COMPLETE" | "PARTIAL" | "INCOMPLETE",
    workflowStatus: project.workflowStatus,
    photoMetadataMissingCount,
    photoDuplicateCount,
  });

  // Combine DB risk flags with dynamic real-time reasoning findings (deduping by title)
  const dbFindings = flags.map((flag) => ({
    severity: flag.severity,
    title: flag.title,
    explanation: flag.explanation,
    evidence: flag.evidence,
    module: flag.module,
  }));
  const findings = [...dbFindings];
  for (const dynamicFinding of dynamicEvaluation.findings) {
    if (!findings.some((f) => f.title === dynamicFinding.title)) {
      findings.push(dynamicFinding);
    }
  }

  const modules = [
    {
      name: "Financial & Temporal",
      status: findings.some((item) => item.module === "Financial & Temporal") ? "AVAILABLE" : "INSUFFICIENT_DATA",
      score: dynamicEvaluation.moduleScores.financialTemporalScore,
      summary: findings.some((item) => item.module === "Financial & Temporal")
        ? `Peer-relative financial and temporal anomaly check: Risk score ${dynamicEvaluation.riskScore}/100.`
        : "Insufficient peer data for a material comparison.",
      evidence: findings.filter((item) => item.module === "Financial & Temporal").map((item) => item.evidence),
    },
    {
      name: "Visual & Spatial",
      status: photos.some((photo) => photo.exifStatus === "Metadata missing") ? "PARTIAL" : "AVAILABLE",
      score: dynamicEvaluation.moduleScores.visualSpatialScore,
      summary: photos.some((photo) => photo.exifStatus === "Metadata missing")
        ? "Metadata missing — manual verification required."
        : "Progress imagery and spatial metadata reviewed.",
      evidence: photos.map((photo) => `${photo.stage}: ${photo.gpsStatus}; ${photo.duplicateStatus}`),
    },
    {
      name: "Satellite Change Detection",
      status: "INCONCLUSIVE",
      score: null,
      summary: "DEMO / SIMULATED SATELLITE RESULT — imagery adapter is not connected to a live imagery provider.",
      evidence: ["Inconclusive — imagery unavailable", "NDVI and NDBI comparison is simulated for demonstration only."],
    },
  ];
  return {
    ...toListItem(project, agency.name),
    mpName: mp.fullName,
    mpCategory: "Lok Sabha",
    mpConstituency: mp.scopeLabel,
    estimatedCost: decimal(project.estimatedCost),
    dateOfSanction: project.dateOfSanction,
    expectedCompletionDate: project.expectedCompletionDate,
    actualCompletionDate: project.actualCompletionDate,
    tenderInvited: project.tenderInvited,
    ucFiled: project.ucFiled,
    dataCompleteness: project.dataCompleteness,
    agencyType: agency.type,
    agencyStateLevel: agency.isStateLevel,
    paymentTotal: payments.reduce((total, payment) => total + decimal(payment.amount), 0),
    progressUpdates: progress.map((item) => ({ date: item.updateDate, stage: item.stage, progress: decimal(item.progress), note: item.note })),
    findings,
    modules,
    photos: photos.map((photo) => ({
      id: String(photo.id),
      stage: photo.stage,
      date: photo.photoDate,
      uploader: photo.uploader,
      gpsStatus: photo.gpsStatus,
      exifStatus: photo.exifStatus,
      duplicateStatus: photo.duplicateStatus,
      imageUrl: photo.imageUrl,
    })),
    payments: payments.map((payment) => ({
      tranche: payment.tranche,
      date: payment.paymentDate,
      amount: decimal(payment.amount),
      approver: payment.approver,
      submittedBy: payment.submittedBy,
    })),
  };
}