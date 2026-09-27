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
  if (parsed.data.stateCode && user.stateCode && user.stateCode !== parsed.data.stateCode) {
    res.status(401).json({ error: "This account is outside the selected state scope." });
    return;
  }
  if (parsed.data.districtId && user.districtId && user.districtId !== parsed.data.districtId) {
    res.status(401).json({ error: "This account is outside the selected district scope." });
    return;
  }
  if (parsed.data.constituencyId && user.constituencyId && user.constituencyId !== parsed.data.constituencyId) {
    res.status(401).json({ error: "This account is outside the selected constituency scope." });
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
    {
      label: "Ministry Administration",
      username: "kavita.sharma",
      password: "Demo@123",
      authority: "MINISTRY",
      scopeLabel: "National monitoring scope",
    },
    {
      label: "State Nodal Authority",
      username: "raghavendra.rao",
      password: "Demo@123",
      authority: "STATE_NODAL",
      scopeLabel: "Andhra Pradesh state scope",
      stateCode: "AP",
    },
    {
      label: "District Nodal Officer",
      username: "suresh.kumar",
      password: "Demo@123",
      authority: "DISTRICT_AUTHORITY",
      scopeLabel: "Anakapalli, Andhra Pradesh",
      stateCode: "AP",
      districtId: "AP-01",
    },
    {
      label: "Lok Sabha MP",
      username: "meenakshi.iyer",
      password: "Demo@123",
      authority: "MP",
      mpCategory: "LOK_SABHA",
      scopeLabel: "AP · Parliamentary Constituency 1",
      stateCode: "AP",
      constituencyId: "AP-LS-01",
    },
    {
      label: "Rajya Sabha MP",
      username: "vikram.varma",
      password: "Demo@123",
      authority: "MP",
      mpCategory: "RAJYA_SABHA",
      scopeLabel: "AP · Anakapalli District (Rajya Sabha)",
      stateCode: "AP",
      districtId: "AP-01",
    },
    {
      label: "Nominated MP",
      username: "sneha.deshmukh",
      password: "Demo@123",
      authority: "MP",
      mpCategory: "NOMINATED",
      scopeLabel: "National oversight (Nominated MP)",
    },
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