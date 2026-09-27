import { Router, type IRouter } from "express";
import { asc, eq } from "drizzle-orm";
import { db, constituenciesTable, districtsTable, statesTable } from "@workspace/db";
import { ListConstituenciesParams, ListConstituenciesResponse, ListDistrictsParams, ListDistrictsResponse, ListStatesResponse } from "@workspace/api-zod";

const router: IRouter = Router();

router.get("/administration/states", async (_req, res): Promise<void> => {
  const rows = await db.select().from(statesTable).orderBy(asc(statesTable.name));
  res.json(ListStatesResponse.parse(rows));
});

router.get("/administration/states/:stateCode/districts", async (req, res): Promise<void> => {
  const params = ListDistrictsParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  const rows = await db.select().from(districtsTable).where(eq(districtsTable.stateCode, params.data.stateCode)).orderBy(asc(districtsTable.name));
  res.json(ListDistrictsResponse.parse(rows));
});

router.get("/administration/states/:stateCode/constituencies", async (req, res): Promise<void> => {
  const params = ListConstituenciesParams.safeParse(req.params);
  if (!params.success) {
    res.status(400).json({ error: params.error.message });
    return;
  }
  const rows = await db.select().from(constituenciesTable).where(eq(constituenciesTable.stateCode, params.data.stateCode)).orderBy(asc(constituenciesTable.name));
  res.json(ListConstituenciesResponse.parse(rows));
});

export default router;