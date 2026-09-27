import pg from '../lib/db/node_modules/pg/lib/index.js';

const client = new pg.Client({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });

const CATEGORIES = [
  { key: 'ROADS_AND_BRIDGES', weight: 35, template: 'Construction and widening of CC road with cross-drainage at ' },
  { key: 'WATER_AND_SANITATION', weight: 25, template: 'Installation of community RO water purification plant and piped supply at ' },
  { key: 'COMMUNITY_HALLS_AND_INFRASTRUCTURE', weight: 20, template: 'Multi-purpose community hall and civic amenities centre at ' },
  { key: 'EDUCATION_AND_LIBRARIES', weight: 10, template: 'Smart classroom infrastructure and digital public library at ' },
  { key: 'HEALTH_AND_PUBLIC_SAFETY', weight: 5, template: 'Primary health sub-centre modernization and emergency care post at ' },
  { key: 'SOLAR_ENERGY_AND_LIGHTING', weight: 5, template: 'High-mast solar street lighting and decentralized solar grid at ' },
];

function pickCategory(seed) {
  const roll = seed % 100;
  let cumulative = 0;
  for (const cat of CATEGORIES) {
    cumulative += cat.weight;
    if (roll < cumulative) return cat;
  }
  return CATEGORIES[0];
}

async function run() {
  await client.connect();
  console.log('Connected to PostgreSQL.');

  // 1. Create project_escalations table if not exists
  await client.query(`
    CREATE TABLE IF NOT EXISTS project_escalations (
      id SERIAL PRIMARY KEY,
      work_id TEXT NOT NULL REFERENCES projects(work_id),
      escalated_by_user_id TEXT NOT NULL REFERENCES users(id),
      escalated_by_role TEXT NOT NULL,
      target_role TEXT NOT NULL,
      target_scope TEXT NOT NULL,
      escalation_reason TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'PENDING',
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
      resolved_at TIMESTAMPTZ,
      resolution_reason TEXT
    );
  `);
  console.log('Verified project_escalations table.');

  // 2. Fetch all projects with their location
  const { rows: projects } = await client.query(`
    SELECT work_id, state_code, district_id, mp_id 
    FROM projects 
    ORDER BY work_id
  `);
  console.log(`Fetched ${projects.length} projects for category & fiscal trend re-alignment.`);

  // Fetch district names
  const { rows: districtRows } = await client.query(`SELECT id, name FROM districts`);
  const districtMap = new Map(districtRows.map(d => [d.id, d.name]));

  // Fiscal year profiles: [year, countShare, avgProgress, avgExpRatio]
  const FISCAL_PROFILES = [
    { year: '2021-22', progressMin: 85, progressMax: 100, expMin: 0.88, expMax: 1.00 },
    { year: '2022-23', progressMin: 70, progressMax: 90,  expMin: 0.72, expMax: 0.88 },
    { year: '2023-24', progressMin: 45, progressMax: 70,  expMin: 0.48, expMax: 0.70 },
    { year: '2024-25', progressMin: 25, progressMax: 50,  expMin: 0.25, expMax: 0.48 },
    { year: '2025-26', progressMin: 10, progressMax: 30,  expMin: 0.08, expMax: 0.25 },
  ];

  // Prepare batch updates
  const batchSize = 500;
  for (let i = 0; i < projects.length; i += batchSize) {
    const chunk = projects.slice(i, i + batchSize);
    
    for (let j = 0; j < chunk.length; j++) {
      const p = chunk[j];
      const index = i + j;
      const districtName = districtMap.get(p.district_id) || p.district_id;
      
      // Determine category using varied hash
      const catSeed = (index * 7 + (p.state_code.charCodeAt(0) * 13) + (p.district_id.charCodeAt(p.district_id.length - 1) * 19)) % 100;
      const cat = pickCategory(catSeed);
      const description = `${cat.template}${districtName} Sector ${((index % 9) + 1)}`;

      // Determine fiscal year: distribute 2021-22 to 2025-26 with realistic variation
      const fyProfileIndex = (index * 3 + catSeed) % FISCAL_PROFILES.length;
      const fyProfile = FISCAL_PROFILES[fyProfileIndex];
      const fiscalYear = fyProfile.year;
      const yearStart = parseInt(fiscalYear.slice(0, 4));

      // Sanctioned amount: ₹12 Lakhs to ₹1.8 Crores
      const sanctioned = 1200000 + ((index * 7919) % 16800000);
      const estCost = Math.round(sanctioned * (1.0 + ((index % 17) * 0.02)));

      // Progress & Expenditure based on FY profile
      const progressSpread = fyProfile.progressMax - fyProfile.progressMin;
      const progressValue = Math.min(100, fyProfile.progressMin + (index % progressSpread));
      
      const expSpread = fyProfile.expMax - fyProfile.expMin;
      const expRatio = fyProfile.expMin + ((index % 100) / 100) * expSpread;
      const expenditure = Math.min(sanctioned, Math.round(sanctioned * expRatio));

      // Dates
      const sanctionMonth = String((index % 12) + 1).padStart(2, '0');
      const sanctionDay = String((index % 28) + 1).padStart(2, '0');
      const dateOfSanction = `${yearStart}-${sanctionMonth}-${sanctionDay}`;
      const expectedCompletion = `${yearStart + 1}-12-31`;

      // Status
      const status = progressValue >= 90 ? 'COMPLETED' : progressValue < 20 ? 'DELAYED' : 'IN_PROGRESS';

      // Workflow status: some escalated projects for State and District
      let workflowStatus = 'OPEN';
      if (index === 0) {
        workflowStatus = 'ESCALATED'; // Anakapalli Primary Demo is escalated!
      } else if (index % 37 === 0) {
        workflowStatus = 'ESCALATED';
      } else if (index % 53 === 0) {
        workflowStatus = 'ESCALATED_STATE';
      } else if (index % 19 === 0) {
        workflowStatus = 'UNDER_REVIEW';
      } else if (index % 23 === 0) {
        workflowStatus = 'RESOLVED';
      }

      await client.query(`
        UPDATE projects SET
          work_category = $1,
          work_description = $2,
          fiscal_year = $3,
          sanctioned_amount = $4,
          estimated_cost = $5,
          expenditure_incurred = $6,
          physical_progress_pct = $7,
          date_of_sanction = $8,
          expected_completion_date = $9,
          status = $10,
          workflow_status = $11,
          updated_at = NOW()
        WHERE work_id = $12
      `, [cat.key, description, fiscalYear, String(sanctioned), String(estCost), String(expenditure), String(progressValue), dateOfSanction, expectedCompletion, status, workflowStatus, p.work_id]);

      // If escalated, insert into project_escalations
      if (workflowStatus === 'ESCALATED' || workflowStatus === 'ESCALATED_STATE') {
        const isFromDistrict = workflowStatus === 'ESCALATED';
        const role = isFromDistrict ? 'DISTRICT_AUTHORITY' : 'STATE_NODAL';
        const targetRole = isFromDistrict ? 'STATE_NODAL' : 'MINISTRY';
        const targetScope = isFromDistrict ? p.state_code : 'NATIONAL';
        const reason = isFromDistrict
          ? `Disbursement milestone divergence detected in ${districtName}: 74% expenditure incurred against ${progressValue}% verified physical progress. Ground agency failed to furnish second-stage geo-tagged photographs and vendor measurement book.`
          : `State Nodal Review for ${p.state_code}: Agency non-compliance regarding repeated cost revision and unfiled Utilization Certificate. Escalated to MoSPI Ministry Desk for inter-departmental audit.`;

        await client.query(`
          INSERT INTO project_escalations (
            work_id, escalated_by_user_id, escalated_by_role, target_role, target_scope, escalation_reason, status, created_at
          ) VALUES ($1, $2, $3, $4, $5, $6, 'PENDING', NOW())
          ON CONFLICT DO NOTHING
        `, [p.work_id, isFromDistrict ? 'DST-REAL-01' : 'STA-REAL-01', role, targetRole, targetScope, reason]);

        await client.query(`
          INSERT INTO flag_actions (
            work_id, user_id, role, action, timestamp, reason, from_status, to_status
          ) VALUES ($1, $2, $3, 'ESCALATE', NOW(), $4, 'OPEN', $5)
        `, [p.work_id, isFromDistrict ? 'DST-REAL-01' : 'STA-REAL-01', role, reason, workflowStatus]);
      }
    }
    console.log(`Processed chunk ${i + 1} to ${Math.min(i + batchSize, projects.length)}...`);
  }

  console.log('\n--- VERIFICATION: AP State Category Breakdown ---');
  const apCatRes = await client.query(`
    SELECT work_category, count(*) 
    FROM projects 
    WHERE state_code = 'AP' 
    GROUP BY work_category 
    ORDER BY count(*) DESC
  `);
  console.table(apCatRes.rows);

  console.log('\n--- VERIFICATION: Anakapalli District (AP-01) Category Breakdown ---');
  const anakapalliCatRes = await client.query(`
    SELECT work_category, count(*) 
    FROM projects 
    WHERE district_id = 'AP-01' 
    GROUP BY work_category 
    ORDER BY count(*) DESC
  `);
  console.table(anakapalliCatRes.rows);

  console.log('\n--- VERIFICATION: AP Fiscal Trend (Sanction & Expenditure) ---');
  const apFiscalRes = await client.query(`
    SELECT fiscal_year, count(*) as project_count, 
           round(sum(sanctioned_amount::numeric)/10000000, 2) as sanctioned_cr,
           round(sum(expenditure_incurred::numeric)/10000000, 2) as expenditure_cr
    FROM projects 
    WHERE state_code = 'AP' 
    GROUP BY fiscal_year 
    ORDER BY fiscal_year ASC
  `);
  console.table(apFiscalRes.rows);

  console.log('\n--- VERIFICATION: Escalated Projects Count ---');
  const escRes = await client.query(`
    SELECT workflow_status, count(*) 
    FROM projects 
    WHERE workflow_status IN ('ESCALATED', 'ESCALATED_STATE')
    GROUP BY workflow_status
  `);
  console.table(escRes.rows);

  await client.end();
}

run().catch(console.error);
