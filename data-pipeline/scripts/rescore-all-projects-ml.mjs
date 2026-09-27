import pg from '../lib/db/node_modules/pg/lib/index.js';
import { evaluateProjectRisk } from '../artifacts/api-server/src/lib/ml-risk-engine.ts';

const client = new pg.Client({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });

async function run() {
  await client.connect();
  console.log('Connected to PostgreSQL for ML Risk Engine batch re-evaluation.');

  // 1. Fetch asset inspection counts per project
  console.log('Aggregating asset verification telemetry...');
  const assetRes = await client.query(`
    SELECT work_id, 
           COUNT(CASE WHEN exif_status = 'Metadata missing' THEN 1 END) AS missing_meta,
           COUNT(CASE WHEN duplicate_status = 'Potential reuse' THEN 1 END) AS dup_count
    FROM assets
    GROUP BY work_id
  `);
  const assetMap = new Map();
  for (const row of assetRes.rows) {
    assetMap.set(row.work_id, {
      missingMeta: parseInt(row.missing_meta, 10) || 0,
      dupCount: parseInt(row.dup_count, 10) || 0,
    });
  }

  // 2. Fetch escalation reasons
  console.log('Aggregating escalation logs...');
  const escRes = await client.query(`
    SELECT work_id, escalation_reason
    FROM project_escalations
    WHERE status = 'PENDING'
  `);
  const escMap = new Map();
  for (const row of escRes.rows) {
    escMap.set(row.work_id, row.escalation_reason);
  }

  // 3. Fetch all projects
  console.log('Fetching all projects for ML inference...');
  const { rows: projects } = await client.query(`
    SELECT work_id, estimated_cost, sanctioned_amount, expenditure_incurred, physical_progress_pct,
           date_of_sanction, expected_completion_date, actual_completion_date,
           tender_invited, uc_filed, data_completeness, workflow_status
    FROM projects
    ORDER BY work_id
  `);
  console.log(`Processing ${projects.length} project records through trained ML pipeline...`);

  let updatedCount = 0;
  const batchSize = 400;

  for (let i = 0; i < projects.length; i += batchSize) {
    const chunk = projects.slice(i, i + batchSize);
    
    // Build batch update query using VALUES
    const valueClauses = [];
    const params = [];
    let pIdx = 1;

    for (const p of chunk) {
      const assetData = assetMap.get(p.work_id) || { missingMeta: 0, dupCount: 0 };
      const escalationReason = escMap.get(p.work_id);

      const evaluation = evaluateProjectRisk({
        workId: p.work_id,
        estimatedCost: Number(p.estimated_cost),
        sanctionedAmount: Number(p.sanctioned_amount),
        expenditureIncurred: Number(p.expenditure_incurred),
        physicalProgressPct: Number(p.physical_progress_pct),
        dateOfSanction: p.date_of_sanction,
        expectedCompletionDate: p.expected_completion_date,
        actualCompletionDate: p.actual_completion_date,
        tenderInvited: Boolean(p.tender_invited),
        ucFiled: Boolean(p.uc_filed),
        dataCompleteness: p.data_completeness,
        workflowStatus: p.workflow_status,
        photoMetadataMissingCount: assetData.missingMeta,
        photoDuplicateCount: assetData.dupCount,
        escalationReason,
      });

      valueClauses.push(`($${pIdx}::text, $${pIdx + 1}::numeric, $${pIdx + 2}::text)`);
      params.push(p.work_id, evaluation.riskScore, evaluation.riskLevel);
      pIdx += 3;
      updatedCount++;
    }

    const updateQuery = `
      UPDATE projects AS p
      SET 
        risk_score = v.risk_score,
        risk_level = v.risk_level,
        updated_at = NOW()
      FROM (VALUES ${valueClauses.join(', ')}) AS v(work_id, risk_score, risk_level)
      WHERE p.work_id = v.work_id;
    `;

    await client.query(updateQuery, params);
    if ((i + batchSize) % 2000 === 0 || i + batchSize >= projects.length) {
      console.log(`  Scored and updated ${Math.min(i + batchSize, projects.length)} / ${projects.length} records...`);
    }
  }

  console.log(`\nSuccessfully evaluated and updated ${updatedCount} records via ML pipeline.`);

  // =========================================================================
  // VERIFICATION AUDIT
  // =========================================================================
  console.log('\n======================== VERIFICATION AUDIT ========================');

  // Check specific cited projects
  const sampleRes = await client.query(`
    SELECT work_id, risk_score, risk_level, workflow_status, data_completeness,
           physical_progress_pct, expenditure_incurred, sanctioned_amount
    FROM projects
    WHERE work_id IN ('WS-AP-2022-00757', 'WS-AP-2024-02269', 'WS-AP-2025-00505', 'WS-AP-2022-05797')
    ORDER BY work_id
  `);
  console.log('\n1. User-Reported Benchmark Projects (Must NOT be 8.00 or 0.00):');
  console.table(sampleRes.rows);

  // Check distribution of scores
  const distRes = await client.query(`
    SELECT 
      MIN(risk_score) AS min_score,
      MAX(risk_score) AS max_score,
      ROUND(AVG(risk_score), 2) AS avg_score,
      COUNT(DISTINCT risk_score) AS distinct_scores,
      COUNT(CASE WHEN risk_score = 8.00 THEN 1 END) AS count_static_eight,
      COUNT(CASE WHEN risk_score = 0.00 THEN 1 END) AS count_zero
    FROM projects
  `);
  console.log('\n2. Score Statistical Distribution:');
  console.table(distRes.rows);

  // Check risk levels
  const levelRes = await client.query(`
    SELECT risk_level, count(*) AS count, ROUND(AVG(risk_score), 2) AS avg_score
    FROM projects
    GROUP BY risk_level
    ORDER BY count DESC
  `);
  console.log('\n3. Risk Level Breakdown:');
  console.table(levelRes.rows);

  // Check escalated projects risk scores
  const escScoreRes = await client.query(`
    SELECT 
      workflow_status,
      MIN(risk_score) AS min_score,
      MAX(risk_score) AS max_score,
      ROUND(AVG(risk_score), 2) AS avg_score,
      COUNT(*) AS total_count
    FROM projects
    WHERE workflow_status IN ('ESCALATED', 'ESCALATED_STATE')
    GROUP BY workflow_status
  `);
  console.log('\n4. Escalated Projects Risk Scores (Must be >= 70.0):');
  console.table(escScoreRes.rows);

  await client.end();
}

run().catch(console.error);
