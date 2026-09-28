import Badge from "./ui/Badge";
import { EXTRACTION_STATUS_LABELS } from "../utils/disclaimers";
import type { ExtractionStatus } from "../types";

const TONES: Record<ExtractionStatus, "neutral" | "info" | "success" | "warning" | "danger"> = {
  pending: "neutral",
  processing: "info",
  completed: "success",
  // Warnings, not errors: the document is fine, we simply cannot read text
  // that was never in it.
  needs_ocr: "warning",
  failed: "danger",
};

/**
 * One badge for one extraction outcome, worded identically everywhere.
 *
 * The labels come from `disclaimers.ts` rather than being spelled out per
 * screen, so "Needs OCR" cannot drift into "Unreadable" on one page and
 * "Scanned" on another.
 */
export default function ExtractionBadge({ status }: { status: ExtractionStatus }) {
  const tone = TONES[status] ?? "neutral";
  const label = EXTRACTION_STATUS_LABELS[status] ?? status;
  return <Badge tone={tone}>{label}</Badge>;
}
