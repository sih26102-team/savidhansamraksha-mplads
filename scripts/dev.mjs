import { execSync, spawn } from 'node:child_process';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { ensureDatabaseRunning } from './start-db.mjs';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const rootDir = path.resolve(__dirname, '..');
const apiDir = path.resolve(rootDir, 'backend-data');
const webDir = path.resolve(rootDir, 'frontend-dashboard');

async function main() {
  await ensureDatabaseRunning();

  console.log('\n======================================================');
  console.log('   SavidhanSamraksha Monitoring Platform - Dev Runner');
  console.log('======================================================\n');
  console.log('[Dev] Building API Server...');
  execSync(`"${process.execPath}" ./build.mjs`, { cwd: apiDir, stdio: 'inherit' });

  console.log('[Dev] Starting API Server on http://localhost:5000...');
  const apiProcess = spawn(
    process.execPath,
    ['--enable-source-maps', './dist/index.mjs'],
    {
      cwd: apiDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        PORT: '5000',
        DATABASE_URL: process.env.DATABASE_URL || 'postgresql://postgres@127.0.0.1:5433/savidhan',
        SESSION_SECRET: process.env.SESSION_SECRET || 'savidhan-samraksha-development-secret',
      },
    }
  );

  console.log('[Dev] Starting Frontend on http://localhost:5173...\n');
  const viteJs = path.resolve(webDir, 'node_modules/vite/bin/vite.js');
  const webProcess = spawn(
    process.execPath,
    [viteJs, '--config', 'vite.config.js', '--host', '0.0.0.0'],
    {
      cwd: webDir,
      stdio: 'inherit',
      env: {
        ...process.env,
        PORT: '5173',
        BASE_PATH: '/',
        API_URL: 'http://127.0.0.1:5000',
      },
    }
  );

  const cleanup = () => {
    console.log('\n[Dev] Shutting down development servers...');
    try { apiProcess.kill(); } catch {}
    try { webProcess.kill(); } catch {}
    process.exit(0);
  };

  process.on('SIGINT', cleanup);
  process.on('SIGTERM', cleanup);
  process.on('exit', cleanup);
}

main().catch((err) => {
  console.error('[Dev] Failed to start:', err);
  process.exit(1);
});
