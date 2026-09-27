import { boolean, pgTable, text } from "drizzle-orm/pg-core";
import { constituenciesTable, districtsTable, statesTable } from "./administration";

export const usersTable = pgTable("users", {
  id: text("id").primaryKey(),
  fullName: text("full_name").notNull(),
  username: text("username").notNull().unique(),
  designation: text("designation").notNull(),
  role: text("role").notNull(),
  stateCode: text("state_code").references(() => statesTable.code),
  districtId: text("district_id").references(() => districtsTable.id),
  constituencyId: text("constituency_id").references(() => constituenciesTable.id),
  passwordHash: text("password_hash").notNull(),
  scopeId: text("scope_id").notNull(),
  scopeLabel: text("scope_label").notNull(),
  readOnly: boolean("read_only").notNull().default(false),
});

export type User = typeof usersTable.$inferSelect;