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

export type FlagAction = typeof flagActionsTable.$inferSelect;