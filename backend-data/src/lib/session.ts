import { createHmac, timingSafeEqual } from "node:crypto";
import type { Request, Response } from "express";
import type { User } from "@workspace/db";

const COOKIE_NAME = "ss_session";
const SESSION_SECRET = process.env.SESSION_SECRET ?? "savidhan-samraksha-development-secret";

export type SessionUser = Pick<
  User,
  | "id"
  | "fullName"
  | "username"
  | "designation"
  | "role"
  | "stateCode"
  | "districtId"
  | "constituencyId"
  | "scopeLabel"
  | "readOnly"
>;

function encode(value: string): string {
  return Buffer.from(value).toString("base64url");
}

function sign(input: string): string {
  return createHmac("sha256", SESSION_SECRET).update(input).digest("base64url");
}

export function createSessionToken(user: SessionUser): string {
  const header = encode(JSON.stringify({ alg: "HS256", typ: "JWT" }));
  const payload = encode(
    JSON.stringify({
      sub: user.id,
      user,
      iat: Math.floor(Date.now() / 1000),
    }),
  );
  return `${header}.${payload}.${sign(`${header}.${payload}`)}`;
}

export function readSessionToken(token: string | undefined): SessionUser | null {
  if (!token) return null;
  const [header, payload, signature] = token.split(".");
  if (!header || !payload || !signature) return null;
  const expected = sign(`${header}.${payload}`);
  const left = Buffer.from(signature);
  const right = Buffer.from(expected);
  if (left.length !== right.length || !timingSafeEqual(left, right)) return null;
  try {
    const decoded = JSON.parse(Buffer.from(payload, "base64url").toString("utf8")) as {
      user?: SessionUser;
    };
    return decoded.user ?? null;
  } catch {
    return null;
  }
}

export function getSessionUser(req: Request): SessionUser | null {
  return readSessionToken(req.cookies?.[COOKIE_NAME]);
}

export function setSessionCookie(res: Response, user: SessionUser): void {
  res.cookie(COOKIE_NAME, createSessionToken(user), {
    httpOnly: true,
    sameSite: "lax",
    secure: process.env.NODE_ENV === "production",
    maxAge: 8 * 60 * 60 * 1000,
  });
}

export function clearSessionCookie(res: Response): void {
  res.clearCookie(COOKIE_NAME);
}