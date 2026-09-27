import app from "./app";
import { logger } from "./lib/logger";
import { ensureSeeded } from "./lib/seed";

const rawPort = process.env["PORT"] || "5000";

const port = Number(rawPort);

if (Number.isNaN(port) || port <= 0) {
  throw new Error(`Invalid PORT value: "${rawPort}"`);
}

async function start(): Promise<void> {
  await ensureSeeded();
  app.listen(port, (err) => {
    if (err) {
      logger.error({ err }, "Error listening on port");
      process.exit(1);
    }
    logger.info({ port }, "Server listening");
  });
}

start().catch((err: unknown) => {
  logger.error({ err }, "Unable to start API server");
  process.exit(1);
});
