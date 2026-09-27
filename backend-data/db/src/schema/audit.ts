import { timestamp, integer, pgTable, text } from "drizzle-orm/pg-core";
import { projectsTable } from "./projects";
import { usersTable } from "./users";

export const flagActionsTable = pgTable("flag_actions", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  userId: text("user_id")
    .notNull()
    .references(() => usersTable.id),
  role: text("role").notNull(),
  action: text("action").notNull(),
  timestamp: timestamp("timestamp", { withTimezone: true }).notNull().defaultNow(),
  reason: text("reason").notNull(),
  fromStatus: text("from_status"),
  toStatus: text("to_status"),
});

export const projectEscalationsTable = pgTable("project_escalations", {
  id: integer("id").primaryKey().generatedAlwaysAsIdentity(),
  workId: text("work_id")
    .notNull()
    .references(() => projectsTable.workId),
  escalatedByUserId: text("escalated_by_user_id")
    .notNull()
    .references(() => usersTable.id),
  escalatedByRole: text("escalated_by_role").notNull(),
  targetRole: text("target_role").notNull(),
  targetScope: text("target_scope").notNull(),
  escalationReason: text("escalation_reason").notNull(),
  status: text("status").notNull().default("PENDING"),
  createdAt: timestamp("created_at", { withTimezone: true }).notNull().defaultNow(),
  resolvedAt: timestamp("resolved_at", { withTimezone: true }),
  resolutionReason: text("resolution_reason"),
});

export type FlagAction = typeof flagActionsTable.$inferSelect;
export type ProjectEscalation = typeof projectEscalationsTable.$inferSelect;