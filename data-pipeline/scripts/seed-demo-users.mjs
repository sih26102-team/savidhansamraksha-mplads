import pg from '../lib/db/node_modules/pg/lib/index.js';
import crypto from 'node:crypto';

const hashPassword = (p) => crypto.createHash('sha256').update(p).digest('hex');
const client = new pg.Client({ connectionString: 'postgresql://postgres@127.0.0.1:5433/savidhan' });

async function run() {
  await client.connect();
  const pwd = hashPassword('Demo@123');
  const demoUsers = [
    {
      id: 'MIN-REAL-01',
      full_name: 'Dr. Kavita Sharma',
      username: 'kavita.sharma',
      designation: 'Ministry Administration Officer',
      role: 'MINISTRY',
      state_code: null,
      district_id: null,
      constituency_id: null,
      password_hash: pwd,
      scope_id: 'NATIONAL',
      scope_label: 'National monitoring scope',
      read_only: false
    },
    {
      id: 'STA-REAL-01',
      full_name: 'Raghavendra Rao',
      username: 'raghavendra.rao',
      designation: 'State Nodal Authority',
      role: 'STATE_NODAL',
      state_code: 'AP',
      district_id: null,
      constituency_id: null,
      password_hash: pwd,
      scope_id: 'AP',
      scope_label: 'Andhra Pradesh state scope',
      read_only: false
    },
    {
      id: 'DST-REAL-01',
      full_name: 'Suresh Kumar',
      username: 'suresh.kumar',
      designation: 'District Nodal Officer',
      role: 'DISTRICT_AUTHORITY',
      state_code: 'AP',
      district_id: 'AP-01',
      constituency_id: null,
      password_hash: pwd,
      scope_id: 'AP-01',
      scope_label: 'Anakapalli, Andhra Pradesh',
      read_only: false
    },
    {
      id: 'MP-REAL-01',
      full_name: 'Meenakshi Iyer',
      username: 'meenakshi.iyer',
      designation: 'Member of Parliament (Lok Sabha)',
      role: 'MP',
      state_code: 'AP',
      district_id: null,
      constituency_id: 'AP-LS-01',
      password_hash: pwd,
      scope_id: 'AP-LS-01',
      scope_label: 'Andhra Pradesh · Andhra Pradesh Parliamentary Constituency 1',
      read_only: true
    },
    {
      id: 'MP-REAL-02',
      full_name: 'Vikram Varma',
      username: 'vikram.varma',
      designation: 'Member of Parliament (Rajya Sabha)',
      role: 'MP',
      state_code: 'AP',
      district_id: 'AP-01',
      constituency_id: null,
      password_hash: pwd,
      scope_id: 'AP-01',
      scope_label: 'Andhra Pradesh · Anakapalli District (Rajya Sabha)',
      read_only: true
    },
    {
      id: 'MP-REAL-03',
      full_name: 'Sneha Deshmukh',
      username: 'sneha.deshmukh',
      designation: 'Member of Parliament (Nominated)',
      role: 'MP',
      state_code: null,
      district_id: null,
      constituency_id: null,
      password_hash: pwd,
      scope_id: 'NATIONAL',
      scope_label: 'National Oversight (Nominated MP)',
      read_only: true
    }
  ];

  for (const u of demoUsers) {
    await client.query(`
      INSERT INTO users (id, full_name, username, designation, role, state_code, district_id, constituency_id, password_hash, scope_id, scope_label, read_only)
      VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12)
      ON CONFLICT (username) DO UPDATE SET
        full_name = EXCLUDED.full_name,
        designation = EXCLUDED.designation,
        role = EXCLUDED.role,
        state_code = EXCLUDED.state_code,
        district_id = EXCLUDED.district_id,
        constituency_id = EXCLUDED.constituency_id,
        password_hash = EXCLUDED.password_hash,
        scope_id = EXCLUDED.scope_id,
        scope_label = EXCLUDED.scope_label,
        read_only = EXCLUDED.read_only
    `, [u.id, u.full_name, u.username, u.designation, u.role, u.state_code, u.district_id, u.constituency_id, u.password_hash, u.scope_id, u.scope_label, u.read_only]);
    console.log('Upserted user:', u.username);
  }

  const res = await client.query(`
    SELECT username, full_name, role, state_code, district_id, constituency_id, scope_label 
    FROM users 
    WHERE username IN ('kavita.sharma', 'raghavendra.rao', 'suresh.kumar', 'meenakshi.iyer', 'vikram.varma', 'sneha.deshmukh')
  `);
  console.log('\nVerified Realistic Demo Users in DB:');
  console.table(res.rows);
  await client.end();
}

run().catch(console.error);
