/**
 * Operational Audit & Live Verification Script for ML Risk Pipeline
 * 
 * Tests:
 * 1. Runtime Isolation Forest model execution (verifying dynamic non-static inference).
 * 2. Feature vector extraction from project payloads.
 * 3. Dynamic reasoning engine deriving natural language explanations from metric deltas.
 * 4. Comparative benchmark:
 *    - Payload A: Clean, low-risk baseline
 *    - Payload B: Anomalous, high-risk outlier (divergence, cost escalation, UC omission)
 */

import { evaluateProjectRisk, extractFeatureVector } from '../artifacts/api-server/src/lib/ml-risk-engine.ts';

console.log('='.repeat(70));
console.log('  OPERATIONAL AUDIT: MACHINE LEARNING & RISK EXPLANATION ENGINE');
console.log('  SavidhanSamraksha Monitoring Platform');
console.log('='.repeat(70));

// =========================================================================
// TEST PAYLOAD A: Clean, Low-Risk Baseline Project
// =========================================================================
const payloadA = {
  workId: 'TEST-PROJ-CLEAN-001',
  estimatedCost: 12000000,          // ₹1.20 Cr
  sanctionedAmount: 12000000,       // ₹1.20 Cr (1.0x ratio - on budget)
  expenditureIncurred: 4800000,     // ₹0.48 Cr (40% utilized)
  physicalProgressPct: 42,          // 42% completed (divergence: -2% - normal)
  dateOfSanction: '2025-06-01T00:00:00.000Z',
  expectedCompletionDate: '2026-06-01T00:00:00.000Z',
  actualCompletionDate: null,
  tenderInvited: true,
  ucFiled: false,                   // Not yet due (expenditure <= 50%)
  dataCompleteness: 'COMPLETE',
  photoMetadataMissingCount: 0,
  photoDuplicateCount: 0,
};

// =========================================================================
// TEST PAYLOAD B: Anomalous, High-Risk Outlier Project
// =========================================================================
const payloadB = {
  workId: 'TEST-PROJ-ANOMALOUS-002',
  estimatedCost: 20000000,          // ₹2.00 Cr original estimate
  sanctionedAmount: 28000000,       // ₹2.80 Cr (+40% cost escalation!)
  expenditureIncurred: 25200000,    // ₹2.52 Cr (90% disbursed!)
  physicalProgressPct: 18,          // Only 18% physical progress (+72% divergence!)
  dateOfSanction: '2024-01-01T00:00:00.000Z',
  expectedCompletionDate: '2025-01-01T00:00:00.000Z', // 14+ months overdue!
  actualCompletionDate: null,
  tenderInvited: true,
  ucFiled: false,                   // UC omitted despite 90% disbursement!
  dataCompleteness: 'PARTIAL',
  photoMetadataMissingCount: 2,     // Missing geotags
  photoDuplicateCount: 1,           // Image hash collision
};

console.log('\n[Step 1/4] Verifying Feature Vector Extraction:');
const featuresA = extractFeatureVector(payloadA);
const featuresB = extractFeatureVector(payloadB);

console.log('\nFeature Vector A (Clean):');
console.table({
  'Cost Ratio (Sanctioned/Est)': featuresA.costRatio.toFixed(2),
  'Expenditure Rate': `${(featuresA.expenditureRate * 100).toFixed(1)}%`,
  'Physical Progress': `${(featuresA.progressRate * 100).toFixed(1)}%`,
  'Milestone Divergence': `${(featuresA.progressExpenditureDivergence * 100).toFixed(1)}%`,
  'Time Elapsed Ratio': featuresA.timeElapsedRatio.toFixed(2),
  'Governance Score': featuresA.governanceComplianceScore.toFixed(2),
  'Evidence Score': featuresA.evidenceIntegrityScore.toFixed(2),
});

console.log('\nFeature Vector B (Anomalous):');
console.table({
  'Cost Ratio (Sanctioned/Est)': featuresB.costRatio.toFixed(2),
  'Expenditure Rate': `${(featuresB.expenditureRate * 100).toFixed(1)}%`,
  'Physical Progress': `${(featuresB.progressRate * 100).toFixed(1)}%`,
  'Milestone Divergence': `${(featuresB.progressExpenditureDivergence * 100).toFixed(1)}%`,
  'Time Elapsed Ratio': featuresB.timeElapsedRatio.toFixed(2),
  'Governance Score': featuresB.governanceComplianceScore.toFixed(2),
  'Evidence Score': featuresB.evidenceIntegrityScore.toFixed(2),
});

console.log('\n[Step 2/4] Executing Live Model Inference (Isolation Forest + Multi-Factor Anomaly Engine)...');
const evalA = evaluateProjectRisk(payloadA);
const evalB = evaluateProjectRisk(payloadB);

console.log('\n============================== EVALUATION RESULTS ==============================');
console.log(`Payload A (Clean):`);
console.log(`  Work ID:             ${evalA.workId}`);
console.log(`  Dynamic Risk Score:  ${evalA.riskScore} / 100`);
console.log(`  Assigned Risk Level: ${evalA.riskLevel}`);
console.log(`  Anomaly Confidence:  ${evalA.anomalyConfidence}`);
console.log(`  Financial/Temporal:  ${evalA.moduleScores.financialTemporalScore}/100`);
console.log(`  Visual/Spatial:      ${evalA.moduleScores.visualSpatialScore}/100`);
console.log(`  Dynamic Findings:    ${evalA.findings.length} finding(s) generated.`);
evalA.findings.forEach((f, i) => {
  console.log(`    [${i + 1}] [${f.severity}] ${f.title}`);
  console.log(`        Reasoning: ${f.explanation}`);
  console.log(`        Evidence:  ${f.evidence}`);
});

console.log('\n--------------------------------------------------------------------------------');
console.log(`Payload B (Anomalous):`);
console.log(`  Work ID:             ${evalB.workId}`);
console.log(`  Dynamic Risk Score:  ${evalB.riskScore} / 100`);
console.log(`  Assigned Risk Level: ${evalB.riskLevel}`);
console.log(`  Anomaly Confidence:  ${evalB.anomalyConfidence}`);
console.log(`  Financial/Temporal:  ${evalB.moduleScores.financialTemporalScore}/100`);
console.log(`  Visual/Spatial:      ${evalB.moduleScores.visualSpatialScore}/100`);
console.log(`  Dynamic Findings:    ${evalB.findings.length} finding(s) generated.`);
evalB.findings.forEach((f, i) => {
  console.log(`    [${i + 1}] [${f.severity}] ${f.title}`);
  console.log(`        Reasoning: ${f.explanation}`);
  console.log(`        Evidence:  ${f.evidence}`);
});

console.log('\n[Step 3/4] Runtime Dynamic Verification Checks:');
const assert = (condition, msg) => {
  if (!condition) {
    console.error(`  ❌ FAILED: ${msg}`);
    process.exit(1);
  }
  console.log(`  ✓ PASSED: ${msg}`);
};

assert(evalA.riskScore < 40, `Payload A scored low risk (${evalA.riskScore} < 40)`);
assert(evalA.riskLevel === 'LOW', `Payload A classified as LOW (got ${evalA.riskLevel})`);
assert(evalB.riskScore >= 70, `Payload B scored high risk (${evalB.riskScore} >= 70)`);
assert(evalB.riskLevel === 'HIGH', `Payload B classified as HIGH (got ${evalB.riskLevel})`);
assert(evalB.findings.some(f => f.title.includes('Divergence')), 'Payload B dynamic explanation identified financial-physical divergence');
assert(evalB.findings.some(f => f.title.includes('Escalation')), 'Payload B dynamic explanation identified cost escalation');
assert(evalB.findings.some(f => f.title.includes('Utilization Certificate')), 'Payload B dynamic explanation identified missing UC');
assert(evalB.findings.some(f => f.title.includes('Schedule')), 'Payload B dynamic explanation identified timeline overrun');

console.log('\n[Step 4/4] Non-Static Determinism & Delta Responsiveness Check:');
// Slightly alter divergence and check that score and dynamic text reflect the change
const alteredPayload = { ...payloadB, physicalProgressPct: 85 }; // now divergence is only 5%
const alteredEval = evaluateProjectRisk(alteredPayload);
console.log(`  Original Score: ${evalB.riskScore} -> Score with 85% progress: ${alteredEval.riskScore}`);
assert(alteredEval.riskScore < evalB.riskScore, 'Model dynamically reduces risk score when physical progress increases');
console.log('  ✓ PASSED: Runtime model is active, dynamic, and responds directly to input feature deltas.');

console.log('\n='.repeat(70));
console.log('  OPERATIONAL AUDIT COMPLETED SUCCESSFULLY: ALL CHECKS PASSED');
console.log('='.repeat(70));
