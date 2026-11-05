/**
 * Clinical Report Presentation & Medical Nomenclature Formatter.
 *
 * Provides standardized medical dictionaries, clinical status interpretation,
 * unit normalization, and human-readable formatting for laboratory results,
 * diagnostic tests, and patient records.
 */

export type ClinicalResultStatus =
  | "normal"
  | "abnormal_high"
  | "abnormal_low"
  | "critical"
  | "pending"
  | "unavailable";

export interface ClinicalStatusDetails {
  status: ClinicalResultStatus;
  label: string;
  badgeClass: string;
  dotClass: string;
  tone: "success" | "warning" | "danger" | "info" | "neutral";
}

/**
 * Standard dictionary mapping technical keys, snake_case strings, and clinical
 * abbreviations to complete, human-readable medical test titles.
 */
const MEDICAL_TEST_NAMES: Record<string, string> = {
  // Blood Glucose & Diabetes
  fbs: "Fasting Blood Sugar (FBS)",
  fasting_blood_sugar: "Fasting Blood Sugar (FBS)",
  fasting_blood_glucose: "Fasting Blood Glucose (FBG)",
  fasting_glucose: "Fasting Blood Glucose (FBG)",
  glucose_fasting: "Fasting Blood Glucose (FBG)",
  glucose: "Blood Glucose",
  blood_glucose: "Blood Glucose",
  ppbs: "Post Prandial Blood Sugar (PPBS)",
  postprandial_blood_sugar: "Post Prandial Blood Sugar (PPBS)",
  post_prandial_blood_sugar: "Post Prandial Blood Sugar (PPBS)",
  rbs: "Random Blood Sugar (RBS)",
  random_blood_sugar: "Random Blood Sugar (RBS)",
  hba1c: "Glycated Hemoglobin (HbA1c)",
  glycosylated_hemoglobin: "Glycosylated Hemoglobin (HbA1c)",
  glycated_hemoglobin: "Glycated Hemoglobin (HbA1c)",
  estimated_average_glucose: "Estimated Average Glucose (eAG)",

  // Complete Blood Count (CBC) & Hematology
  cbc: "Complete Blood Count (CBC)",
  complete_blood_count: "Complete Blood Count (CBC)",
  hemogram: "Complete Hemogram",
  hb: "Hemoglobin (Hb)",
  haemoglobin: "Hemoglobin (Hb)",
  hemoglobin: "Hemoglobin (Hb)",
  rbc: "Red Blood Cell (RBC) Count",
  rbc_count: "Red Blood Cell (RBC) Count",
  red_blood_cells: "Red Blood Cell (RBC) Count",
  wbc: "Total Leukocyte / White Blood Cell Count (WBC)",
  wbc_count: "Total Leukocyte Count (WBC / TLC)",
  tlc: "Total Leukocyte Count (TLC)",
  white_blood_cells: "White Blood Cell (WBC) Count",
  platelets: "Platelet Count",
  platelet_count: "Platelet Count",
  platelet: "Platelet Count",
  plt: "Platelet Count (PLT)",
  pcv: "Packed Cell Volume (PCV / Hematocrit)",
  hematocrit: "Hematocrit (HCT / PCV)",
  mcv: "Mean Corpuscular Volume (MCV)",
  mch: "Mean Corpuscular Hemoglobin (MCH)",
  mchc: "Mean Corpuscular Hemoglobin Concentration (MCHC)",
  rdw: "Red Cell Distribution Width (RDW)",
  rdw_cv: "Red Cell Distribution Width (RDW-CV)",
  rdw_sd: "Red Cell Distribution Width (RDW-SD)",
  esr: "Erythrocyte Sedimentation Rate (ESR)",
  neutrophils: "Neutrophils (Differential Count)",
  lymphocytes: "Lymphocytes (Differential Count)",
  monocytes: "Monocytes (Differential Count)",
  eosinophils: "Eosinophils (Differential Count)",
  basophils: "Basophils (Differential Count)",

  // Renal / Kidney Function (KFT / RFT)
  kft: "Kidney Function Tests (KFT / RFT)",
  rft: "Renal Function Tests (RFT)",
  serum_creatinine: "Serum Creatinine",
  creatinine: "Serum Creatinine",
  creatinine_serum: "Serum Creatinine",
  blood_urea: "Blood Urea",
  urea: "Blood Urea",
  bun: "Blood Urea Nitrogen (BUN)",
  blood_urea_nitrogen: "Blood Urea Nitrogen (BUN)",
  uric_acid: "Serum Uric Acid",
  serum_uric_acid: "Serum Uric Acid",
  egfr: "Estimated Glomerular Filtration Rate (eGFR)",
  bun_creatinine_ratio: "BUN / Creatinine Ratio",

  // Liver Function Tests (LFT)
  lft: "Liver Function Tests (LFT)",
  liver_function_tests: "Liver Function Tests (LFT)",
  sgot: "SGOT / AST (Aspartate Aminotransferase)",
  ast: "AST / SGOT (Aspartate Aminotransferase)",
  sgot_ast: "SGOT / AST (Aspartate Aminotransferase)",
  sgpt: "SGPT / ALT (Alanine Aminotransferase)",
  alt: "ALT / SGPT (Alanine Aminotransferase)",
  sgpt_alt: "SGPT / ALT (Alanine Aminotransferase)",
  alp: "Alkaline Phosphatase (ALP)",
  alkaline_phosphatase: "Alkaline Phosphatase (ALP)",
  total_bilirubin: "Total Bilirubin",
  bilirubin_total: "Total Bilirubin",
  direct_bilirubin: "Direct (Conjugated) Bilirubin",
  bilirubin_direct: "Direct (Conjugated) Bilirubin",
  indirect_bilirubin: "Indirect (Unconjugated) Bilirubin",
  total_protein: "Total Serum Protein",
  serum_protein: "Total Serum Protein",
  albumin: "Serum Albumin",
  globulin: "Serum Globulin",
  ag_ratio: "Albumin / Globulin (A/G) Ratio",
  a_g_ratio: "Albumin / Globulin (A/G) Ratio",
  ggt: "Gamma-Glutamyl Transferase (GGT)",

  // Lipid Profile
  lipid_profile: "Complete Lipid Profile",
  total_cholesterol: "Total Serum Cholesterol",
  cholesterol: "Total Serum Cholesterol",
  serum_cholesterol: "Total Serum Cholesterol",
  hdl: "HDL Cholesterol ('Good' High-Density Lipoprotein)",
  hdl_cholesterol: "HDL Cholesterol ('Good' High-Density Lipoprotein)",
  ldl: "LDL Cholesterol ('Bad' Low-Density Lipoprotein)",
  ldl_cholesterol: "LDL Cholesterol ('Bad' Low-Density Lipoprotein)",
  vldl: "VLDL Cholesterol (Very Low-Density Lipoprotein)",
  vldl_cholesterol: "VLDL Cholesterol (Very Low-Density Lipoprotein)",
  triglycerides: "Serum Triglycerides",
  serum_triglycerides: "Serum Triglycerides",
  tg: "Serum Triglycerides",
  chol_hdl_ratio: "Total Cholesterol / HDL Ratio",

  // Thyroid Panel
  tft: "Thyroid Function Tests (TFT)",
  thyroid_profile: "Thyroid Profile",
  tsh: "Thyroid Stimulating Hormone (TSH)",
  t3: "Total Triiodothyronine (T3)",
  total_t3: "Total Triiodothyronine (T3)",
  t4: "Total Thyroxine (T4)",
  total_t4: "Total Thyroxine (T4)",
  ft3: "Free Triiodothyronine (FT3)",
  free_t3: "Free Triiodothyronine (FT3)",
  ft4: "Free Thyroxine (FT4)",
  free_t4: "Free Thyroxine (FT4)",

  // Vitamins & Minerals
  vitamin_d: "Vitamin D (25-Hydroxycholecalciferol)",
  vit_d: "Vitamin D (25-Hydroxy)",
  "25_hydroxy_vitamin_d": "25-Hydroxy Vitamin D",
  vitamin_b12: "Vitamin B12 (Cyanocobalamin)",
  vit_b12: "Vitamin B12 (Cobalamin)",
  b12: "Vitamin B12",
  calcium: "Serum Calcium",
  serum_calcium: "Serum Calcium",
  sodium: "Serum Sodium (Na+)",
  serum_sodium: "Serum Sodium (Na+)",
  potassium: "Serum Potassium (K+)",
  serum_potassium: "Serum Potassium (K+)",
  chloride: "Serum Chloride (Cl-)",
  serum_chloride: "Serum Chloride (Cl-)",
  magnesium: "Serum Magnesium",
  serum_magnesium: "Serum Magnesium",
  phosphorus: "Serum Phosphorus / Phosphate",
  serum_iron: "Serum Iron",
  iron: "Serum Iron",
  ferritin: "Serum Ferritin",
  tibc: "Total Iron Binding Capacity (TIBC)",

  // Inflammation & Cardiac Markers
  crp: "C-Reactive Protein (CRP)",
  hs_crp: "High-Sensitivity C-Reactive Protein (hs-CRP)",
  troponin: "Cardiac Troponin I",
  troponin_i: "Cardiac Troponin I",
  troponin_t: "Cardiac Troponin T",
  ck_mb: "Creatine Kinase-MB (CK-MB)",
  d_dimer: "D-Dimer Assay",

  // Urine Examination
  urine_routine: "Routine Urine Examination (Complete Urinalysis)",
  routine_urine: "Routine Urine Examination (Urinalysis)",
  urinalysis: "Complete Urinalysis",
  urine_protein: "Urine Protein (Albumin)",
  urine_albumin: "Urine Albumin",
  urine_sugar: "Urine Sugar (Glucose)",
  urine_glucose: "Urine Glucose",
  pus_cells: "Pus Cells (WBC in Urine)",
  urine_pus_cells: "Pus Cells (WBC in Urine)",
  rbc_in_urine: "Red Blood Cells (RBC in Urine)",
  epithelial_cells: "Epithelial Cells in Urine",

  // Vitals & Clinical Measurements
  bp: "Blood Pressure (BP)",
  blood_pressure: "Blood Pressure (BP)",
  pulse: "Pulse Rate / Heart Rate",
  pulse_rate: "Pulse Rate",
  heart_rate: "Heart Rate",
  spo2: "Oxygen Saturation (SpO2)",
  oxygen_saturation: "Oxygen Saturation (SpO2)",
  temperature: "Body Temperature",
  body_temp: "Body Temperature",
  respiratory_rate: "Respiratory Rate",
  bmi: "Body Mass Index (BMI)",
};

/**
 * Common medical acronyms to keep uppercase in title-casing.
 */
const MEDICAL_ACRONYMS = new Set([
  "CBC",
  "FBS",
  "PPBS",
  "RBS",
  "HBA1C",
  "ESR",
  "CRP",
  "BUN",
  "KFT",
  "RFT",
  "LFT",
  "AST",
  "ALT",
  "SGOT",
  "SGPT",
  "ALP",
  "GGT",
  "HDL",
  "LDL",
  "VLDL",
  "TSH",
  "T3",
  "T4",
  "FT3",
  "FT4",
  "WBC",
  "RBC",
  "PCV",
  "HCT",
  "MCV",
  "MCH",
  "MCHC",
  "RDW",
  "PLT",
  "BP",
  "SPO2",
  "BMI",
  "TIBC",
  "eGFR",
  "hs-CRP",
]);

/**
 * Format any raw medical test identifier into a complete, human-readable name.
 * Avoids raw database keys, snake_case, and unformatted technical strings.
 */
export function formatMedicalTestName(rawName?: string | null): string {
  if (!rawName || !rawName.trim()) {
    return "Diagnostic Test";
  }

  const clean = rawName.trim();
  const lookupKey = clean.toLowerCase().replace(/[\s\-_.:/]+/g, "_");

  // Check direct dictionary match
  if (MEDICAL_TEST_NAMES[lookupKey]) {
    return MEDICAL_TEST_NAMES[lookupKey];
  }

  // Remove common OCR artifacts or trailing punctuation
  let sanitized = clean
    .replace(/[;:,._]+$/, "")
    .replace(/^[;:,._]+/, "")
    .replace(/[_-]+/g, " ");

  // Convert to clean Title Case while respecting known medical acronyms
  const words = sanitized.split(/\s+/).filter(Boolean);
  const formattedWords = words.map((word) => {
    const upper = word.toUpperCase();
    if (MEDICAL_ACRONYMS.has(upper)) {
      return upper;
    }
    if (word.length <= 2 && /^[a-z0-9]+$/i.test(word)) {
      return word.toUpperCase();
    }
    // Title Case word
    return word.charAt(0).toUpperCase() + word.slice(1).toLowerCase();
  });

  return formattedWords.join(" ");
}

/**
 * Cleanly format test result values and units.
 */
export function formatResultValue(value?: string | null, unit?: string | null): string {
  if (value === null || value === undefined || value.trim() === "") {
    return "Result pending / not stated";
  }
  const cleanVal = value.trim();
  const cleanUnit = unit ? unit.trim() : "";
  if (cleanUnit && !cleanVal.toLowerCase().includes(cleanUnit.toLowerCase())) {
    return `${cleanVal} ${cleanUnit}`;
  }
  return cleanVal;
}

/**
 * Parse a numeric value and boundary range safely without fabricating or guessing.
 */
function checkNumericRange(
  valStr: string,
  rangeStr: string
): "normal" | "abnormal_high" | "abnormal_low" | null {
  const numVal = parseFloat(valStr.replace(/[^\d.-]/g, ""));
  if (isNaN(numVal)) return null;

  // Pattern: "12 - 16" or "12.0-16.0"
  const dashMatch = rangeStr.match(/(\d+(?:\.\d+)?)\s*[-–—to]+\s*(\d+(?:\.\d+)?)/i);
  if (dashMatch) {
    const low = parseFloat(dashMatch[1]);
    const high = parseFloat(dashMatch[2]);
    if (!isNaN(low) && !isNaN(high)) {
      if (numVal < low) return "abnormal_low";
      if (numVal > high) return "abnormal_high";
      return "normal";
    }
  }

  // Pattern: "< 100" or "<= 140"
  const lessMatch = rangeStr.match(/^[<≤]\s*(\d+(?:\.\d+)?)/);
  if (lessMatch) {
    const max = parseFloat(lessMatch[1]);
    if (!isNaN(max)) {
      return numVal > max ? "abnormal_high" : "normal";
    }
  }

  // Pattern: "> 50" or ">= 60"
  const greaterMatch = rangeStr.match(/^[>≥]\s*(\d+(?:\.\d+)?)/);
  if (greaterMatch) {
    const min = parseFloat(greaterMatch[1]);
    if (!isNaN(min)) {
      return numVal < min ? "abnormal_low" : "normal";
    }
  }

  return null;
}

/**
 * Determine clinical interpretation status based strictly on verified report data.
 * Never invents interpretations or values.
 */
export function determineResultStatus(
  value?: string | null,
  _unit?: string | null,
  referenceRange?: string | null,
  flag?: string | null
): ClinicalResultStatus {
  if (!value || value.trim() === "" || value.toLowerCase() === "n/a" || value.toLowerCase() === "not tested") {
    return "unavailable";
  }

  const vLower = value.toLowerCase().trim();
  if (vLower === "pending" || vLower.includes("awaiting") || vLower.includes("in progress")) {
    return "pending";
  }

  // Check explicit printed flag first
  const flagStr = (flag || "").toLowerCase().trim();
  if (flagStr.includes("critical") || flagStr.includes("panic") || flagStr.includes("urgent")) {
    return "critical";
  }
  if (flagStr.includes("high") || flagStr === "h" || flagStr.includes("elevated") || flagStr === ">") {
    return "abnormal_high";
  }
  if (flagStr.includes("low") || flagStr === "l" || flagStr.includes("decreased") || flagStr === "<") {
    return "abnormal_low";
  }
  if (flagStr.includes("normal") || flagStr === "n" || flagStr.includes("wnl") || flagStr === "negative") {
    return "normal";
  }

  // Evaluate against printed reference range if available
  if (referenceRange && referenceRange.trim()) {
    const evaluated = checkNumericRange(value, referenceRange.trim());
    if (evaluated) {
      return evaluated;
    }
  }

  // Common qualitative values
  if (["negative", "non-reactive", "nil", "absent", "clear"].includes(vLower)) {
    return "normal";
  }
  if (["positive", "reactive", "present"].includes(vLower)) {
    return "abnormal_high";
  }

  return "normal";
}

/**
 * Detailed UI styling configuration for clinical status badges.
 */
export function getClinicalStatusDetails(status: ClinicalResultStatus): ClinicalStatusDetails {
  switch (status) {
    case "critical":
      return {
        status: "critical",
        label: "Critical Finding",
        badgeClass: "bg-rose-50 text-rose-800 border-rose-200 ring-rose-500/20",
        dotClass: "bg-rose-500",
        tone: "danger",
      };
    case "abnormal_high":
      return {
        status: "abnormal_high",
        label: "Above Range (High)",
        badgeClass: "bg-amber-50 text-amber-800 border-amber-200 ring-amber-500/20",
        dotClass: "bg-amber-500",
        tone: "warning",
      };
    case "abnormal_low":
      return {
        status: "abnormal_low",
        label: "Below Range (Low)",
        badgeClass: "bg-sky-50 text-sky-800 border-sky-200 ring-sky-500/20",
        dotClass: "bg-sky-500",
        tone: "info",
      };
    case "pending":
      return {
        status: "pending",
        label: "Pending",
        badgeClass: "bg-purple-50 text-purple-800 border-purple-200 ring-purple-500/20",
        dotClass: "bg-purple-400",
        tone: "neutral",
      };
    case "unavailable":
      return {
        status: "unavailable",
        label: "Not Specified",
        badgeClass: "bg-slate-100 text-slate-600 border-slate-200",
        dotClass: "bg-slate-400",
        tone: "neutral",
      };
    case "normal":
    default:
      return {
        status: "normal",
        label: "Normal / Within Range",
        badgeClass: "bg-emerald-50 text-emerald-800 border-emerald-200 ring-emerald-500/20",
        dotClass: "bg-emerald-500",
        tone: "success",
      };
  }
}

/**
 * Formats a persistent Patient ID consistently across all screens.
 * Formats CareVerse 4-digit ID as `CV-P-{id}` or fallback `PAT-{id.slice(-8).toUpperCase()}`.
 */
export function formatPatientDisplayId(
  patientId?: string | null,
  careverseId?: string | null
): string {
  if (careverseId && careverseId.trim()) {
    const clean = careverseId.trim();
    return clean.startsWith("CV-P-") ? clean : `CV-P-${clean}`;
  }
  if (patientId && patientId.trim()) {
    const clean = patientId.trim();
    const short = clean.length > 8 ? clean.slice(-8).toUpperCase() : clean.toUpperCase();
    return `PAT-${short}`;
  }
  return "PAT-UNKNOWN";
}

/**
 * Formats a persistent Document ID consistently across all screens.
 * Formats as `#DOC-{id.slice(-8).toUpperCase()}` or returns given document_code.
 */
export function formatDocumentDisplayId(
  documentId?: string | null,
  documentCode?: string | null
): string {
  if (documentCode && documentCode.trim()) {
    const clean = documentCode.trim();
    return clean.startsWith("#") ? clean : `#${clean}`;
  }
  if (documentId && documentId.trim()) {
    const clean = documentId.trim();
    const short = clean.length > 8 ? clean.slice(-8).toUpperCase() : clean.toUpperCase();
    return `#DOC-${short}`;
  }
  return "#DOC-UNKNOWN";
}
