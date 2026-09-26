import { createHash } from "node:crypto";
import { and, count, eq } from "drizzle-orm";
import { db } from "@workspace/db";
import {
  agenciesTable,
  assetsTable,
  constituenciesTable,
  districtsTable,
  flagActionsTable,
  paymentsTable,
  progressUpdatesTable,
  projectsTable,
  riskFlagsTable,
  statesTable,
  usersTable,
} from "@workspace/db";
import { logger } from "./logger";

const stateSeeds = [
  ["AP", "Andhra Pradesh", ["Anakapalli", "Anantapur", "Chittoor", "East Godavari", "Guntur", "Kakinada", "Krishna", "Nellore", "Prakasam", "Srikakulam", "Tirupati", "Visakhapatnam", "Vizianagaram", "West Godavari"]],
  ["AR", "Arunachal Pradesh", ["Itanagar", "Tawang", "Papum Pare", "East Siang", "West Siang", "Lohit", "Namsai"]],
  ["AS", "Assam", ["Baksa", "Barpeta", "Cachar", "Dibrugarh", "Kamrup", "Lakhimpur", "Nagaon", "Sonitpur", "Tinsukia"]],
  ["BR", "Bihar", ["Araria", "Aurangabad", "Begusarai", "Bhagalpur", "Darbhanga", "Gaya", "Madhubani", "Muzaffarpur", "Nalanda", "Patna", "Purnia", "Samastipur", "Saran", "Vaishali"]],
  ["CG", "Chhattisgarh", ["Balod", "Bastar", "Bilaspur", "Durg", "Janjgir-Champa", "Korba", "Raipur", "Rajnandgaon", "Surguja"]],
  ["GA", "Goa", ["North Goa", "South Goa"]],
  ["GJ", "Gujarat", ["Ahmedabad", "Amreli", "Banaskantha", "Bhavnagar", "Gandhinagar", "Jamnagar", "Kachchh", "Rajkot", "Surat", "Vadodara"]],
  ["HR", "Haryana", ["Ambala", "Bhiwani", "Faridabad", "Gurugram", "Hisar", "Karnal", "Kurukshetra", "Panipat", "Rohtak", "Sirsa", "Sonipat"]],
  ["HP", "Himachal Pradesh", ["Bilaspur", "Chamba", "Hamirpur", "Kangra", "Kinnaur", "Kullu", "Mandi", "Shimla", "Sirmaur", "Solan", "Una"]],
  ["JH", "Jharkhand", ["Bokaro", "Chatra", "Deoghar", "Dhanbad", "Dumka", "East Singhbhum", "Giridih", "Hazaribagh", "Ranchi", "West Singhbhum"]],
  ["KA", "Karnataka", ["Bengaluru Rural", "Belagavi", "Ballari", "Chikkaballapur", "Dakshina Kannada", "Dharwad", "Hassan", "Kalaburagi", "Mysuru", "Shivamogga", "Tumakuru", "Udupi"]],
  ["KL", "Kerala", ["Alappuzha", "Ernakulam", "Idukki", "Kannur", "Kasaragod", "Kollam", "Kottayam", "Kozhikode", "Malappuram", "Palakkad", "Thiruvananthapuram", "Thrissur"]],
  ["MP", "Madhya Pradesh", ["Bhopal", "Chhindwara", "Gwalior", "Indore", "Jabalpur", "Mandla", "Morena", "Rewa", "Sagar", "Satna", "Ujjain"]],
  ["MH", "Maharashtra", ["Ahmednagar", "Aurangabad", "Beed", "Bhandara", "Chandrapur", "Dhule", "Jalgaon", "Kolhapur", "Latur", "Nashik", "Nagpur", "Nanded", "Pune", "Raigad", "Satara", "Solapur", "Thane", "Wardha", "Yavatmal"]],
  ["MN", "Manipur", ["Bishnupur", "Chandel", "Churachandpur", "Imphal East", "Imphal West", "Senapati", "Thoubal", "Ukhrul"]],
  ["ML", "Meghalaya", ["East Garo Hills", "East Khasi Hills", "Jaintia Hills", "Ri-Bhoi", "South Garo Hills", "West Garo Hills", "West Khasi Hills"]],
  ["MZ", "Mizoram", ["Aizawl", "Champhai", "Kolasib", "Lawngtlai", "Lunglei", "Mamit", "Serchhip"]],
  ["NL", "Nagaland", ["Dimapur", "Kohima", "Mokokchung", "Mon", "Peren", "Tuensang", "Wokha", "Zunheboto"]],
  ["OD", "Odisha", ["Angul", "Balangir", "Balasore", "Cuttack", "Dhenkanal", "Ganjam", "Jagatsinghpur", "Jajpur", "Kalahandi", "Khordha", "Koraput", "Mayurbhanj", "Puri", "Sambalpur", "Sundargarh"]],
  ["PB", "Punjab", ["Amritsar", "Bathinda", "Faridkot", "Fatehgarh Sahib", "Fazilka", "Gurdaspur", "Hoshiarpur", "Jalandhar", "Ludhiana", "Mansa", "Patiala", "Sangrur"]],
  ["RJ", "Rajasthan", ["Ajmer", "Alwar", "Banswara", "Baran", "Barmer", "Bharatpur", "Bhilwara", "Bikaner", "Bundi", "Chittorgarh", "Jaipur", "Jaisalmer", "Jhalawar", "Jodhpur", "Kota", "Nagaur", "Pali", "Sikar", "Udaipur"]],
  ["SK", "Sikkim", ["East Sikkim", "North Sikkim", "South Sikkim", "West Sikkim"]],
  ["TN", "Tamil Nadu", ["Ariyalur", "Chengalpattu", "Chennai", "Coimbatore", "Cuddalore", "Dharmapuri", "Dindigul", "Erode", "Kancheepuram", "Madurai", "Namakkal", "Salem", "Thanjavur", "Tiruchirappalli", "Tirunelveli", "Vellore", "Virudhunagar"]],
  ["TS", "Telangana", ["Adilabad", "Bhadradri Kothagudem", "Hyderabad", "Jagtial", "Karimnagar", "Khammam", "Mahabubnagar", "Medak", "Nalgonda", "Nizamabad", "Rangareddy", "Sangareddy", "Warangal", "Yadadri Bhuvanagiri"]],
  ["TR", "Tripura", ["Dhalai", "Gomati", "Khowai", "North Tripura", "Sepahijala", "South Tripura", "Unakoti", "West Tripura"]],
  ["UK", "Uttarakhand", ["Almora", "Bageshwar", "Chamoli", "Champawat", "Dehradun", "Haridwar", "Nainital", "Pauri Garhwal", "Pithoragarh", "Rudraprayag", "Tehri Garhwal", "Udham Singh Nagar", "Uttarkashi"]],
  ["UP", "Uttar Pradesh", ["Agra", "Aligarh", "Allahabad", "Azamgarh", "Bareilly", "Gorakhpur", "Jhansi", "Kanpur Nagar", "Lucknow", "Mathura", "Meerut", "Moradabad", "Prayagraj", "Varanasi"]],
  ["WB", "West Bengal", ["Bankura", "Bardhaman", "Birbhum", "Darjeeling", "Hooghly", "Howrah", "Jalpaiguri", "Kolkata", "Malda", "Murshidabad", "Nadia", "North 24 Parganas", "South 24 Parganas"]],
  ["AN", "Andaman and Nicobar Islands", ["Nicobar", "North and Middle Andaman", "South Andaman"]],
  ["CH", "Chandigarh", ["Chandigarh"]],
  ["DN", "Dadra and Nagar Haveli and Daman and Diu", ["Daman", "Diu", "Dadra and Nagar Haveli"]],
  ["DL", "Delhi", ["Central Delhi", "East Delhi", "New Delhi", "North Delhi", "North East Delhi", "North West Delhi", "South Delhi", "South East Delhi", "South West Delhi", "West Delhi"]],
  ["JK", "Jammu and Kashmir", ["Anantnag", "Baramulla", "Budgam", "Jammu", "Kathua", "Pulwama", "Srinagar", "Udhampur"]],
  ["LA", "Ladakh", ["Leh", "Kargil"]],
  ["LD", "Lakshadweep", ["Lakshadweep"]],
  ["PY", "Puducherry", ["Karaikal", "Mahe", "Puducherry", "Yanam"]],
] as const;

const firstNames = ["Aarav", "Aditi", "Ananya", "Arjun", "Bhavna", "Chaitanya", "Deepak", "Devika", "Ishaan", "Kavya", "Kiran", "Lakshmi", "Manish", "Meera", "Naveen", "Neha", "Nikhil", "Pallavi", "Prakash", "Priya", "Rahul", "Radhika", "Ravi", "Rekha", "Sanjay", "Shalini", "Siddharth", "Sneha", "Vikram", "Vijaya"];
const lastNames = ["Agarwal", "Babu", "Chandra", "Das", "Deshmukh", "Gupta", "Iyer", "Joshi", "Khan", "Kulkarni", "Menon", "Mishra", "Nair", "Patel", "Pillai", "Rao", "Reddy", "Sharma", "Singh", "Varma"];
const categories = ["Roads", "Community Halls", "Drinking Water", "Sanitation", "Drainage", "Education", "Health", "Public Amenities", "Civic Infrastructure"];
const agencyTypes = ["Public Works Department", "Panchayat Raj & Rural Development Department", "Rural Water Supply & Sanitation Department", "School Education Department", "Health & Family Welfare Department", "Public Health Engineering Department", "Roads & Buildings Department", "Zilla Parishad", "Municipal Council"];

const hashPassword = (password: string) => createHash("sha256").update(password).digest("hex");
const pad = (value: number, width = 4) => String(value).padStart(width, "0");

type DistrictSeed = { id: string; name: string; stateCode: string };
type ConstituencySeed = { id: string; name: string; stateCode: string };

let seeded = false;
let seedPromise: Promise<void> | null = null;

export async function ensureSeeded(): Promise<void> {
  if (seeded) return;
  if (seedPromise) return seedPromise;
  seedPromise = seedDatabase().then(() => {
    seeded = true;
  }).catch((error) => {
    seedPromise = null;
    throw error;
  });
  return seedPromise;
}

async function seedDatabase(): Promise<void> {
  const existing = await db.select({ value: count() }).from(statesTable);
  if (Number(existing[0]?.value ?? 0) > 0) {
    return;
  }

  const districts: DistrictSeed[] = [];
  const constituencies: ConstituencySeed[] = [];
  for (const [stateCode, stateName, districtNames] of stateSeeds) {
    for (const [index, name] of districtNames.entries()) {
      districts.push({ id: `${stateCode}-${String(index + 1).padStart(2, "0")}`, name, stateCode });
    }
    const constituencyCount = stateCode === "AP" ? 6 : Math.max(1, Math.ceil(districtNames.length / 4));
    for (let index = 0; index < constituencyCount; index += 1) {
      constituencies.push({ id: `${stateCode}-LS-${pad(index + 1, 2)}`, name: `${stateName} Parliamentary Constituency ${index + 1}`, stateCode });
    }
  }

  await db.insert(statesTable).values(stateSeeds.map(([code, name, districtNames]) => ({ code, name, districtCount: districtNames.length })));
  await db.insert(districtsTable).values(districts);
  await db.insert(constituenciesTable).values(constituencies);

  const users: Array<typeof usersTable.$inferInsert> = [];
  for (let index = 0; index < 10; index += 1) {
    users.push({
      id: `MIN-${pad(index + 1, 3)}`,
      fullName: index === 0 ? "Dr. Kavita Sharma" : `${firstNames[index]} ${lastNames[index]}`,
      username: index === 0 ? "ministry.demo" : `oversight.${firstNames[index].toLowerCase()}`,
      designation: "Ministry Administration Officer",
      role: "MINISTRY",
      stateCode: null,
      districtId: null,
      constituencyId: null,
      passwordHash: hashPassword("Demo@123"),
      scopeId: "NATIONAL",
      scopeLabel: "National monitoring scope",
      readOnly: false,
    });
  }
  for (let index = 0; index < 72; index += 1) {
    const [stateCode, stateName] = stateSeeds[index % stateSeeds.length];
    const isDemo = index === 0;
    users.push({
      id: `STA-${pad(index + 1, 3)}`,
      fullName: isDemo ? "Raghavendra Rao" : `${firstNames[(index + 6) % firstNames.length]} ${lastNames[(index + 3) % lastNames.length]}`,
      username: isDemo ? "state.ap.demo" : `state.${stateCode.toLowerCase()}.${index + 1}`,
      designation: "State Nodal Authority",
      role: "STATE_NODAL",
      stateCode,
      districtId: null,
      constituencyId: null,
      passwordHash: hashPassword("Demo@123"),
      scopeId: stateCode,
      scopeLabel: `${stateName} state scope`,
      readOnly: false,
    });
  }
  for (let index = 0; index < 780; index += 1) {
    const district = districts[index % districts.length];
    const stateName = stateSeeds.find(([code]) => code === district.stateCode)?.[1] ?? district.stateCode;
    const isDemo = index === 0;
    users.push({
      id: `DST-${pad(index + 1, 4)}`,
      fullName: isDemo ? "Suresh Kumar" : `${firstNames[(index + 11) % firstNames.length]} ${lastNames[(index + 7) % lastNames.length]}`,
      username: isDemo ? "district.ap.demo" : `district.${district.stateCode.toLowerCase()}.${index + 1}`,
      designation: "District Nodal Officer",
      role: "DISTRICT_AUTHORITY",
      stateCode: district.stateCode,
      districtId: district.id,
      constituencyId: null,
      passwordHash: hashPassword("Demo@123"),
      scopeId: district.id,
      scopeLabel: `${district.name}, ${stateName}`,
      readOnly: false,
    });
  }
  for (let index = 0; index < 788; index += 1) {
    const constituency = constituencies[index % constituencies.length];
    const stateName = stateSeeds.find(([code]) => code === constituency.stateCode)?.[1] ?? constituency.stateCode;
    const isDemo = index === 0;
    users.push({
      id: `MP-${pad(index + 1, 4)}`,
      fullName: isDemo ? "Meenakshi Iyer" : `${firstNames[(index + 17) % firstNames.length]} ${lastNames[(index + 10) % lastNames.length]}`,
      username: isDemo ? "mp.demo" : `mp.${constituency.stateCode.toLowerCase()}.${index + 1}`,
      designation: "Member of Parliament",
      role: "MP",
      stateCode: constituency.stateCode,
      districtId: null,
      constituencyId: constituency.id,
      passwordHash: hashPassword("Demo@123"),
      scopeId: constituency.id,
      scopeLabel: `${stateName} · ${constituency.name}`,
      readOnly: true,
    });
  }
  for (let offset = 0; offset < users.length; offset += 500) {
    await db.insert(usersTable).values(users.slice(offset, offset + 500));
  }

  const agencies: Array<typeof agenciesTable.$inferInsert> = [];
  for (const [stateCode, stateName] of stateSeeds) {
    for (let index = 0; index < 2; index += 1) {
      agencies.push({
        id: `AG-${stateCode}-STATE-${index + 1}`,
        name: `${agencyTypes[index]} · ${stateName}`,
        type: agencyTypes[index],
        stateCode,
        districtId: null,
        isStateLevel: true,
        isActive: true,
      });
    }
  }
  for (const [districtIndex, district] of districts.entries()) {
    for (let index = 0; index < 2; index += 1) {
      const type = agencyTypes[(districtIndex + index + 2) % agencyTypes.length];
      agencies.push({
        id: `AG-${district.id}-${index + 1}`,
        name: `${type} · ${district.name}`,
        type,
        stateCode: district.stateCode,
        districtId: district.id,
        isStateLevel: false,
        isActive: true,
      });
    }
  }
  for (let offset = 0; offset < agencies.length; offset += 500) {
    await db.insert(agenciesTable).values(agencies.slice(offset, offset + 500));
  }

  const mpUsers = users.filter((user) => user.role === "MP");
  const projects: Array<typeof projectsTable.$inferInsert> = [];
  const progress: Array<typeof progressUpdatesTable.$inferInsert> = [];
  const payments: Array<typeof paymentsTable.$inferInsert> = [];
  const assets: Array<typeof assetsTable.$inferInsert> = [];
  const flags: Array<typeof riskFlagsTable.$inferInsert> = [];
  const today = new Date("2026-09-26T00:00:00Z");
  for (let index = 0; index < 8200; index += 1) {
    const state = stateSeeds[index % stateSeeds.length];
    const district = districts.filter((item) => item.stateCode === state[0])[index % state[2].length];
    const constituency = constituencies.filter((item) => item.stateCode === state[0])[index % constituencies.filter((item) => item.stateCode === state[0]).length];
    const agency = agencies.find((item) => item.districtId === district.id) ?? agencies.find((item) => item.stateCode === state[0])!;
    const isPrimaryDemo = index === 0;
    const anomaly = index % 11 === 0;
    const incomplete = !isPrimaryDemo && index % 23 === 0;
    const onHold = index % 37 === 0;
    const delayed = index % 17 === 0;
    const category = categories[index % categories.length];
    const yearNumber = 2021 + (index % 5);
    const fiscalYear = `${yearNumber}-${String(yearNumber + 1).slice(-2)}`;
    const sanctionDate = `${yearNumber}-${String((index % 9) + 1).padStart(2, "0")}-${String((index % 24) + 1).padStart(2, "0")}`;
    const sanctioned = 800000 + ((index * 137) % 3200000);
    const score = isPrimaryDemo ? 86 : incomplete ? 0 : anomaly ? 62 + (index % 35) : delayed ? 48 + (index % 25) : 8 + (index % 28);
    const riskLevel = incomplete ? "DATA_INCOMPLETE" : score >= 80 ? "HIGH" : score >= 40 ? "MODERATE" : "LOW";
    const description = isPrimaryDemo
      ? "Community hall and public amenity block at Kothuru village"
      : `${category} improvement at ${district.name} block ${String((index % 12) + 1)}`;
    const workId = `WS-${state[0]}-${yearNumber}-${pad(index + 1, 5)}`;
    const progressValue = isPrimaryDemo ? 62 : onHold ? 28 : Math.min(98, 20 + ((index * 7) % 75));
    const expenditure = Math.round(sanctioned * (isPrimaryDemo ? 0.79 : 0.25 + ((index % 55) / 100)));
    const workflowStatus = isPrimaryDemo ? "UNDER_REVIEW" : index % 43 === 0 ? "ESCALATED" : index % 29 === 0 ? "RESOLVED" : "OPEN";
    const mp = mpUsers[index % mpUsers.length];
    projects.push({
      workId,
      mpId: mp.id,
      stateCode: state[0],
      districtId: district.id,
      agencyId: agency.id,
      constituencyId: constituency.id,
      workDescription: description,
      workCategory: category,
      fiscalYear,
      estimatedCost: String(sanctioned + 150000),
      sanctionedAmount: String(sanctioned),
      expenditureIncurred: String(Math.min(sanctioned * (anomaly ? 1.05 : 0.99), expenditure)),
      physicalProgressPct: String(progressValue),
      dateOfSanction: sanctionDate,
      expectedCompletionDate: `${yearNumber + 1}-12-31`,
      actualCompletionDate: progressValue > 90 ? `${yearNumber + 1}-10-15` : null,
      status: onHold ? "ON_HOLD" : progressValue > 90 ? "COMPLETED" : delayed ? "DELAYED" : "IN_PROGRESS",
      tenderInvited: index % 13 !== 0,
      ucFiled: index % 19 !== 0,
      riskScore: score,
      riskLevel,
      dataCompleteness: incomplete ? "INCOMPLETE" : index % 7 === 0 ? "PARTIAL" : "COMPLETE",
      workflowStatus,
      updatedAt: new Date(today.getTime() - (index % 80) * 86400000),
    });
    progress.push({ workId, updateDate: `${yearNumber + 1}-${String((index % 9) + 1).padStart(2, "0")}-15`, stage: progressValue > 85 ? "Finishing works" : progressValue > 50 ? "Civil works" : "Foundation", progress: String(progressValue), note: onHold ? "Work on hold pending local resolution." : `Field update received from ${district.name}.` });
    payments.push({ workId, tranche: "Tranche 1", paymentDate: `${yearNumber + 1}-04-20`, amount: String(Math.round(expenditure * 0.55)), approver: "District Finance Officer", submittedBy: agency.name });
    assets.push({ workId, stage: "Latest field update", photoDate: `${yearNumber + 1}-05-12`, uploader: "District Works Inspector", gpsStatus: index % 23 === 0 ? "Unavailable" : "Verified", exifStatus: index % 23 === 0 ? "Metadata missing" : "Present", duplicateStatus: index % 31 === 0 ? "Potential reuse" : "No match", imageUrl: "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='640' height='360'%3E%3Crect width='640' height='360' fill='%231c3557'/%3E%3Cpath d='M0 270L180 140l110 80 115-125 235 175H0z' fill='%234d7b76'/%3E%3Ccircle cx='485' cy='90' r='42' fill='%23efc46a'/%3E%3C/svg%3E" });
    if (isPrimaryDemo || anomaly || delayed || index % 29 === 0) {
      if (isPrimaryDemo || index % 11 === 0) flags.push({ workId, severity: "HIGH", title: "Cost anomaly", explanation: "Cost per unit is significantly above the district peer median.", evidence: "2.1× the district peer median for comparable community infrastructure.", module: "Financial & Temporal" });
      if (isPrimaryDemo || delayed) flags.push({ workId, severity: "MODERATE", title: "Progress anomaly", explanation: "Physical progress is substantially below peer-relative progress velocity.", evidence: `Reported progress is ${progressValue}% against the district peer trend.`, module: "Financial & Temporal" });
      if (isPrimaryDemo || index % 13 === 0) flags.push({ workId, severity: "MODERATE", title: "Tender anomaly", explanation: "No tender record found for a project where tendering is expected.", evidence: "Tender invitation record is absent from the submitted project file.", module: "Financial & Temporal" });
      if (index % 31 === 0) flags.push({ workId, severity: "ADVISORY", title: "Potential reused image", explanation: "Potential reused image detected.", evidence: "Perceptual hash is close to a nearby project's latest update.", module: "Visual & Spatial" });
    }
  }
  for (let offset = 0; offset < projects.length; offset += 500) await db.insert(projectsTable).values(projects.slice(offset, offset + 500));
  for (let offset = 0; offset < progress.length; offset += 500) await db.insert(progressUpdatesTable).values(progress.slice(offset, offset + 500));
  for (let offset = 0; offset < payments.length; offset += 500) await db.insert(paymentsTable).values(payments.slice(offset, offset + 500));
  for (let offset = 0; offset < assets.length; offset += 500) await db.insert(assetsTable).values(assets.slice(offset, offset + 500));
  for (let offset = 0; offset < flags.length; offset += 500) await db.insert(riskFlagsTable).values(flags.slice(offset, offset + 500));

  const demo = users.find((user) => user.username === "district.ap.demo");
  if (demo) {
    await db.insert(flagActionsTable).values({
      workId: projects[0].workId,
      userId: demo.id,
      role: demo.role,
      action: "REVIEW",
      reason: "Initial synthetic review opened for demonstration.",
      fromStatus: "OPEN",
      toStatus: "UNDER_REVIEW",
    });
  }
  logger.info({ users: users.length, districts: districts.length, projects: projects.length }, "Synthetic demonstration dataset seeded");
}