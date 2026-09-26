import { boolean, pgTable, text } from "drizzle-orm/pg-core";
import { districtsTable, statesTable } from "./administration";

export const agenciesTable = pgTable("agencies", {
  id: text("agency_id").primaryKey(),
  name: text("agency_name").notNull(),
  type: text("agency_type").notNull(),
  stateCode: text("state_code")
    .notNull()
    .references(() => statesTable.code),
  districtId: text("district_id").references(() => districtsTable.id),
  isStateLevel: boolean("is_state_level").notNull().default(false),
  isActive: boolean("is_active").notNull().default(true),
});

export type Agency = typeof agenciesTable.$inferSelect;