import pg from '../lib/db/node_modules/pg/lib/index.js';

const pool = new pg.Pool({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });

async function verify() {
  const targetIds = ['WS-AP-2022-00757', 'WS-AP-2024-02269', 'WS-AP-2025-00505', 'WS-AP-2022-05797'];
  const res = await pool.query(
    "SELECT work_id, risk_score, risk_level, workflow_status, data_completeness FROM projects WHERE work_id = ANY($1::text[])",
    [targetIds]
  );
  console.log("Target Projects:");
  console.table(res.rows);

  const stats = await pool.query(`
    SELECT 
      (SELECT COUNT(*) FROM projects WHERE risk_score = 0) as zeros,
      (SELECT COUNT(*) FROM projects WHERE risk_score = 8) as eights,
      COUNT(*) as total,
      COUNT(DISTINCT risk_score) as distinct_scores,
      MIN(risk_score) as min_score,
      MAX(risk_score) as max_score,
      ROUND(AVG(risk_score), 2) as avg_score
    FROM projects
  `);
  console.log("Database Stats:");
  console.table(stats.rows);

  const escalatedStats = await pool.query(`
    SELECT 
      COUNT(*) as escalated_count,
      MIN(risk_score) as min_escalated_score,
      MAX(risk_score) as max_escalated_score,
      ROUND(AVG(risk_score), 2) as avg_escalated_score
    FROM projects
    WHERE workflow_status IN ('ESCALATED', 'ESCALATED_STATE')
  `);
  console.log("Escalated Projects Stats:");
  console.table(escalatedStats.rows);

  await pool.end();
}

verify().catch(console.error);
