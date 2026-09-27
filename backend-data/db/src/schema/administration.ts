import { integer, pgTable, text } from "drizzle-orm/pg-core";

export const statesTable = pgTable("states", {
  code: text("code").primaryKey(),
  name: text("name").notNull(),
  districtCount: integer("district_count").notNull().default(0),
});

export const districtsTable = pgTable("districts", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  stateCode: text("state_code")
    .notNull()
    .references(() => statesTable.code),
});

export const constituenciesTable = pgTable("constituencies", {
  id: text("id").primaryKey(),
  name: text("name").notNull(),
  stateCode: text("state_code")
    .notNull()
    .references(() => statesTable.code),
});

export type State = typeof statesTable.$inferSelect;
export type District = typeof districtsTable.$inferSelect;
export type Constituency = typeof constituenciesTable.$inferSelect;