import pg from '../lib/db/node_modules/pg/lib/index.js';

const { Client } = pg;

async function check() {
  const client = new Client({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });
  await client.connect();
  try {
    console.log('=== USER STATS ===');
    const userTotal = await client.query('SELECT count(*) FROM users');
    console.log('Total users:', userTotal.rows[0].count);

    const usersByRole = await client.query('SELECT role, count(*) FROM users GROUP BY role ORDER BY count DESC');
    console.log('Users by role:', usersByRole.rows);

    const nullUsers = await client.query("SELECT count(*) FROM users WHERE username IS NULL OR trim(username) = ''");
    console.log('Users with NULL or empty username:', nullUsers.rows[0].count);

    const distinctUsers = await client.query('SELECT count(DISTINCT username) FROM users');
    console.log('Distinct usernames:', distinctUsers.rows[0].count);

    const sampleUsernames = await client.query('SELECT username, role, scope_label FROM users LIMIT 10');
    console.log('Sample usernames:', sampleUsernames.rows);

    console.log('\n=== PROJECT STATS ===');
    const projTotal = await client.query('SELECT count(*) FROM projects');
    console.log('Total projects:', projTotal.rows[0].count);

    const nullCheck = await client.query(`
      SELECT 
        count(*) FILTER (WHERE work_id IS NULL) as null_work_id,
        count(*) FILTER (WHERE sanctioned_amount IS NULL) as null_sanctioned,
        count(*) FILTER (WHERE expenditure_incurred IS NULL) as null_expenditure,
        count(*) FILTER (WHERE physical_progress_pct IS NULL) as null_progress,
        count(*) FILTER (WHERE risk_score IS NULL) as null_risk_score,
        count(*) FILTER (WHERE status IS NULL) as null_status
      FROM projects
    `);
    console.log('Project NULL check:', nullCheck.rows[0]);

    const mpStats = await client.query(`
      SELECT min(cnt) as min_proj, max(cnt) as max_proj, round(avg(cnt), 2) as avg_proj, count(*) as total_mps
      FROM (SELECT mp_id, count(*) as cnt FROM projects GROUP BY mp_id) s
    `);
    console.log('Projects per MP stats:', mpStats.rows[0]);

    const distStats = await client.query(`
      SELECT min(cnt) as min_proj, max(cnt) as max_proj, round(avg(cnt), 2) as avg_proj, count(*) as total_districts
      FROM (SELECT district_id, count(*) as cnt FROM projects GROUP BY district_id) s
    `);
    console.log('Projects per District stats:', distStats.rows[0]);

    const stateStats = await client.query(`
      SELECT state_code, count(*) as cnt 
      FROM projects 
      GROUP BY state_code 
      ORDER BY cnt DESC
    `);
    console.log('State project counts (Total states with projects:', stateStats.rows.length, ')');
    console.log('Top 5 states:', stateStats.rows.slice(0, 5));
    console.log('Bottom 5 states:', stateStats.rows.slice(-5));
  } finally {
    await client.end();
  }
}

check().catch(console.error);
