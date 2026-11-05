 /** Display formatting shared by the record screens. */

const DATE_UNITS = ["KB", "MB", "GB"];

/** 1536 -> "1.5 KB", 2_097_152 -> "2.0 MB". */
export function formatBytes(bytes: number): string {
  if (!Number.isFinite(bytes) || bytes < 0) return "-";
  if (bytes < 1024) return `${Math.round(bytes)} B`;

  let value = bytes;
  let unit = "KB";
  for (const next of DATE_UNITS) {
    if (value < 1024) break;
    value /= 1024;
    unit = next;
  }
  return `${value.toFixed(value < 10 ? 1 : 0)} ${unit}`;
}

 /** Parse a date without the timezone trap. */
function parseDate(value: string): Date | null {
  const bare = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value.trim());
  if (bare) {
    const date = new Date(Number(bare[1]), Number(bare[2]) - 1, Number(bare[3]));
    return Number.isNaN(date.getTime()) ? null : date;
  }
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** The date printed on the document, e.g. "1 Jun 2026". */
export function formatDate(value: string | null | undefined): string {
  if (!value) return "-";
  const date = parseDate(value);
  if (!date) return "-";
  return date.toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** When it was uploaded, e.g. "27 Sep 2026, 10:13". */
export function formatDateTime(value: string | null | undefined): string {
  if (!value) return "-";
  const date = parseDate(value);
  if (!date) return "-";
  return date.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

 /** Human labels for the stored `DocumentCategory` values. */
const CATEGORY_LABELS: Record<string, string> = {
  lab_report: "Lab report",
  prescription: "Prescription",
  discharge_summary: "Discharge summary",
  imaging: "Imaging",
  other: "Document",
};

export function formatCategory(value: string | null | undefined): string {
  if (!value) return "Document";
  return CATEGORY_LABELS[value] ?? value;
}

 /** Human labels for the stored `Gender` values. */
const GENDER_LABELS: Record<string, string> = {
  male: "Male",
  female: "Female",
  other: "Other",
};

export function formatGender(value: string | null | undefined): string {
  if (!value) return "Not recorded";
  return GENDER_LABELS[value] ?? "Not recorded";
}
