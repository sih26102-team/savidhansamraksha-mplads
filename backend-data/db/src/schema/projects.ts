import {
  boolean,
  date,
  integer,
  numeric,
  pgTable,
  text,
  timestamp,
} from "drizzle-orm/pg-core";
import { agenciesTable } from "./agencies";
import { constituenciesTable, districtsTable, statesTable } from "./administration";
import { usersTable } from "./users";

export const projectsTable = pgTable("projects", {
  workId: text("work_id").primaryKey(),
  mpId: text("mp_id")
    .notNull()
    .references(() => usersTable.id),
  stateCode: text("state_code")
    .notNull()
    .references(() => statesTable.code),
  districtId: text("district_id")
    .notNull()
    .references(() => districtsTable.id),
  agencyId: text("agency_id")
    .notNull()
    .references(() => agenciesTable.id),
  constituencyId: text("constituency_id").references(() => constituenciesTable.id),
  workDescription: text("work_description").notNull(),
  workCategory: text("work_category").notNull(),
  fiscalYear: text("fiscal_year").notNull(),
  estimatedCost: numeric("estimated_cost", { precision: 14, scale: 2 }).notNull(),
  sanctionedAmount: numeric("sanctioned_amount", { precision: 14, scale: 2 }).notNull(),
  expenditureIncurred: numeric("expenditure_incurred", { precision: 14, scale: 2 }).notNull(),
  physicalProgressPct: numeric("physical_progress_pct", { precision: 5, scale: 2 }).notNull(),
  dateOfSanction: date("date_of_sanction", { mode: "string" }).notNull(),
  expectedCompletionDate: date("expected_completion_date", { mode: "string" }).notNull(),
  actualCompletionDate: date("actual_completion_date", { mode: "string" }),
  status: text("status").notNull(),
  tenderInvited: boolean("tender_invited").notNull(),
  ucFiled: boolean("uc_filed").notNull(),
  riskScore: numeric("risk_score", { precision: 5, scale: 2 }).notNull(),
  riskLevel: text("risk_level").notNull(),
  dataCompleteness: text("data_completeness").notNull(),
  workflowStatus: text("workflow_status").notNull(),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  updatedAt: timestamp("updated_at", { withTimezone: true }).notNull().defaultNow(),
});

export const progressUpdatesTable = pgTable("progress_updates", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  updateDate: date("update_date", { mode: "string" }).notNull(),
  stage: text("stage").notNull(),
  progress: numeric("progress", { precision: 5, scale: 2 }).notNull(),
  note: text("note").notNull(),
});

export const riskFlagsTable = pgTable("risk_flags", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  severity: text("severity").notNull(),
  title: text("title").notNull(),
  explanation: text("explanation").notNull(),
  evidence: text("evidence").notNull(),
  module: text("module").notNull(),
});

export const paymentsTable = pgTable("payments", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  tranche: text("tranche").notNull(),
  paymentDate: date("payment_date", { mode: "string" }).notNull(),
  amount: numeric("amount", { precision: 14, scale: 2 }).notNull(),
  approver: text("approver").notNull(),
  submittedBy: text("submitted_by").notNull(),
});

export const assetsTable = pgTable("assets", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  stage: text("stage").notNull(),
  photoDate: date("photo_date", { mode: "string" }).notNull(),
  uploader: text("uploader").notNull(),
  gpsStatus: text("gps_status").notNull(),
  exifStatus: text("exif_status").notNull(),
  duplicateStatus: text("duplicate_status").notNull(),
  imageUrl: text("image_url").notNull(),
});

export type Project = typeof projectsTable.$inferSelect;
export type ProgressUpdate = typeof progressUpdatesTable.$inferSelect;
export type RiskFlag = typeof riskFlagsTable.$inferSelect;
export type Payment = typeof paymentsTable.$inferSelect;
export type Asset = typeof assetsTable.$inferSelect;