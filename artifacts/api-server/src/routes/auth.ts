import { Router, type IRouter } from "express";
import { eq } from "drizzle-orm";
import { db, usersTable } from "@workspace/db";
import { GetCurrentUserResponse, GetDemoAccountsResponse, LoginBody, LoginResponse } from "@workspace/api-zod";
import { clearSessionCookie, getSessionUser, setSessionCookie } from "../lib/session";
import { createHash } from "node:crypto";

const router: IRouter = Router();
const hashPassword = (password: string) => createHash("sha256").update(password).digest("hex");

router.post("/auth/login", async (req, res): Promise<void> => {
  const parsed = LoginBody.safeParse(req.body);
  if (!parsed.success) {
    res.status(400).json({ error: parsed.error.message });
    return;
  }
  const [user] = await db.select().from(usersTable).where(eq(usersTable.username, parsed.data.username));
  if (!user || user.role !== parsed.data.authority || user.passwordHash !== hashPassword(parsed.data.password)) {
    res.status(401).json({ error: "Invalid credentials for the selected authority." });
    return;
  }
  if (parsed.data.stateCode && user.stateCode !== parsed.data.stateCode) {
    res.status(401).json({ error: "This account is outside the selected state scope." });
    return;
  }
  if (parsed.data.districtId && user.districtId !== parsed.data.districtId) {
    res.status(401).json({ error: "This account is outside the selected district scope." });
    return;
  }
  const sessionUser = {
    id: user.id,
    fullName: user.fullName,
    username: user.username,
    designation: user.designation,
    role: user.role,
    stateCode: user.stateCode,
    districtId: user.districtId,
    constituencyId: user.constituencyId,
    scopeLabel: user.scopeLabel,
    readOnly: user.readOnly,
  };
  setSessionCookie(res, sessionUser);
  res.json(LoginResponse.parse({ user: sessionUser }));
});

router.get("/auth/demo", (_req, res) => {
  res.json(GetDemoAccountsResponse.parse([
    { label: "MINISTRY", username: "ministry.demo", password: "Demo@123", authority: "MINISTRY", scopeLabel: "National monitoring scope" },
    { label: "STATE", username: "state.ap.demo", password: "Demo@123", authority: "STATE_NODAL", scopeLabel: "Andhra Pradesh state scope" },
    { label: "DISTRICT", username: "district.ap.demo", password: "Demo@123", authority: "DISTRICT_AUTHORITY", scopeLabel: "Anakapalli, Andhra Pradesh" },
    { label: "MP", username: "mp.demo", password: "Demo@123", authority: "MP", scopeLabel: "Andhra Pradesh Parliamentary Constituency 1" },
  ]));
});

router.get("/auth/me", (req, res): void => {
  const user = getSessionUser(req);
  if (!user) {
    res.status(401).json({ error: "Not authenticated" });
    return;
  }
  res.json(GetCurrentUserResponse.parse(user));
});

router.post("/auth/logout", (_req, res) => {
  clearSessionCookie(res);
  res.sendStatus(204);
});

export default router;