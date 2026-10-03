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

/**
 * The same boundary, stated for a doctor reading a patient's records.
 *
 * Separate from the string above because that one is addressed to the person
 * who uploaded the documents, and on a doctor screen "documents you have
 * uploaded" names the wrong person — the doctor uploaded nothing. The claim
 * being made is identical: CAREVERSE stores and extracts, it does not
 * interpret.
 */
export const NOT_A_DIAGNOSIS_READER_NOTICE =
  "You are reading records a patient uploaded and authorized you to see. CAREVERSE stores documents and extracts their text; it does not interpret them, diagnose conditions, or recommend treatment.";

/** Shown on the record-details screen next to extracted text. */
export const EXTRACTION_NOTICE =
  "Extracted text is produced automatically and may be incomplete or misread. Always confirm values against the original document.";

/** Shown when a PDF has no readable embedded text. */
export const OCR_REQUIRED_NOTICE =
  "This PDF contains no readable text. It looks like a scanned or image-only document, so automated extraction was skipped.";

/**
 * Label for a summary the deterministic provider produced.
 *
 * Shown whenever the server reports `is_mock: true`. Phase 4B has no language
 * model at all, so this is not a degraded fallback that happens to be running
 * locally -- it is the only provider that exists, and a reader must be able to
 * tell that from a model's output at a glance rather than by inference.
 */
export const MOCK_SUMMARY_LABEL =
  "Demo summary — assembled deterministically from the records by pattern matching. No language model was used.";

/**
 * What every summary section says when it found nothing.
 *
 * Rendered in place of an empty list, never as a blank. A section with no
 * items and no note is indistinguishable from a section the system decided not
 * to show, which reads as "nothing abnormal here" — a clinical claim this
 * system is not allowed to make on a patient's behalf.
 */
export const EMPTY_SECTION_NOTE = "Not found in the uploaded records.";

export const EXTRACTION_STATUS_LABELS: Record<string, string> = {
  pending: "Queued",
  processing: "Processing",
  completed: "Extracted",
  needs_ocr: "Needs OCR",
  failed: "Extraction failed",
};
