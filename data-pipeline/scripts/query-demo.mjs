import pg from '../lib/db/node_modules/pg/lib/index.js';

const { Client } = pg;
const client = new Client({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });

async function run() {
  await client.connect();
  const res = await client.query(`
    SELECT id, full_name, username, role, state_code, district_id, constituency_id, scope_label 
    FROM users 
    WHERE username LIKE '%.demo' OR id IN ('MIN-001', 'STA-001', 'DIS-0001', 'MP-0001')
  `);
  console.log('Current Demo Accounts:');
  console.table(res.rows);
  await client.end();
}

run().catch(console.error);
