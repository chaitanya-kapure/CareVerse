/**
 * Medical-safety copy (spec section 9).
 *
 * These strings are deliberately centralized. The disclaimer is part of the
 * safety model, not decoration: it must appear on every summary view and
 * must be worded identically everywhere, so it lives in exactly one place
 * and is imported rather than retyped.
 */

/** Attached to every AI-generated summary. */
export const AI_SUMMARY_DISCLAIMER =
  "AI-generated summary of available records. Verify important information with the original medical documents.";

/** Shown wherever a summary is displayed. */
export const NOT_A_DIAGNOSIS_NOTICE =
  "CAREVERSE summarizes documents you have uploaded. It does not diagnose conditions, recommend treatment, or provide medical advice.";

/** Shown on the record-details screen next to extracted text. */
export const EXTRACTION_NOTICE =
  "Extracted text is produced automatically and may be incomplete or misread. Always confirm values against the original document.";

/** Shown when a PDF has no readable embedded text. */
export const OCR_REQUIRED_NOTICE =
  "This PDF contains no readable text. It looks like a scanned or image-only document, so automated extraction was skipped.";

/** Label for a deterministic, non-AI summary produced in development. */
export const MOCK_SUMMARY_LABEL =
  "Demo summary (deterministic fallback — no AI provider configured)";

export const EXTRACTION_STATUS_LABELS: Record<string, string> = {
  pending: "Queued",
  processing: "Processing",
  completed: "Extracted",
  needs_ocr: "Needs OCR",
  failed: "Extraction failed",
};
