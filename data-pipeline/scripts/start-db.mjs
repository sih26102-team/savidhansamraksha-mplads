import { execSync } from 'node:child_process';
import fs from 'node:fs';
import net from 'node:net';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const defaultPgBin = 'C:\\Program Files\\PostgreSQL\\18\\bin';
const pgDataDir = path.join(process.env.USERPROFILE || 'C:\\Users\\bhara', '.postgres-savidhan');
const port = 5433;

function isPortOpen(testPort, host = '127.0.0.1') {
  return new Promise((resolve) => {
    const socket = new net.Socket();
    socket.setTimeout(1000);
    socket.on('connect', () => {
      socket.destroy();
      resolve(true);
    });
    socket.on('timeout', () => {
      socket.destroy();
      resolve(false);
    });
    socket.on('error', () => {
      resolve(false);
    });
    socket.connect(testPort, host);
  });
}

export async function ensureDatabaseRunning() {
  const isOpen = await isPortOpen(port);
  if (isOpen) {
    console.log(`[DB] PostgreSQL is already running on port ${port}.`);
    return;
  }

  console.log(`[DB] Starting PostgreSQL on port ${port}...`);
  const pgCtl = fs.existsSync(path.join(defaultPgBin, 'pg_ctl.exe'))
    ? path.join(defaultPgBin, 'pg_ctl.exe')
    : 'pg_ctl';
  const initDb = fs.existsSync(path.join(defaultPgBin, 'initdb.exe'))
    ? path.join(defaultPgBin, 'initdb.exe')
    : 'initdb';
  const createdb = fs.existsSync(path.join(defaultPgBin, 'createdb.exe'))
    ? path.join(defaultPgBin, 'createdb.exe')
    : 'createdb';

  if (!fs.existsSync(pgDataDir)) {
    console.log(`[DB] Initializing local database cluster at ${pgDataDir}...`);
    execSync(`"${initDb}" -D "${pgDataDir}" -U postgres -A trust`, { stdio: 'inherit' });
  }

  const pidFile = path.join(pgDataDir, 'postmaster.pid');
  if (fs.existsSync(pidFile)) {
    try {
      fs.unlinkSync(pidFile);
    } catch {}
  }

  const logFile = path.join(pgDataDir, 'pg.log');
  execSync(`"${pgCtl}" -D "${pgDataDir}" -o "-p ${port}" -l "${logFile}" start`, { stdio: 'inherit' });

  for (let i = 0; i < 20; i++) {
    await new Promise((r) => setTimeout(r, 500));
    if (await isPortOpen(port)) break;
  }

  try {
    execSync(`"${createdb}" -h 127.0.0.1 -p ${port} -U postgres savidhan`, { stdio: 'ignore' });
  } catch {}

  console.log(`[DB] PostgreSQL ready on port ${port}.`);
}

const currentFile = fileURLToPath(import.meta.url);
if (process.argv[1] && path.resolve(process.argv[1]) === path.resolve(currentFile)) {
  ensureDatabaseRunning().catch((err) => {
    console.error('[DB] Error:', err);
    process.exit(1);
  });
}
