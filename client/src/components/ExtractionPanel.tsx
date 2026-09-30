import Alert from "./ui/Alert";
import { EXTRACTION_NOTICE, OCR_REQUIRED_NOTICE } from "../utils/disclaimers";
import type { MedicalDocumentDetail } from "../types";

/**
 * Who is looking at the record.
 *
 * The medical-safety wording is identical for both -- it is imported from
 * `utils/disclaimers`, never retyped here. The only thing the audience
 * changes is the sentence that suggests a *next action*, because "upload it
 * again" is meaningful to the person who owns the file and meaningless to a
 * doctor who is only permitted to read it.
 */
export type RecordAudience = "patient" | "doctor";

interface ExtractionPanelProps {
  record: MedicalDocumentDetail;
  audience: RecordAudience;
}

/**
 * The honest rendering of whatever extraction produced.
 *
 * The non-success states are kept distinct on purpose: a scan we could not
 * read, a file that would not parse, and a document still being processed.
 * Collapsing them into "no text" would tell the reader the report is blank
 * when in fact CAREVERSE never read it.
 *
 * Shared by the patient's record screen and the doctor's, so a given PDF
 * cannot look like one thing to the person who uploaded it and another to the
 * clinician they authorized. The text is always presented as *extracted* --
 * never as a finding.
 */
export default function ExtractionPanel({ record, audience }: ExtractionPanelProps) {
  if (record.extraction_status === "completed" && record.extracted_text) {
    return (
      <>
        <Alert tone="info" className="mb-3">
          {EXTRACTION_NOTICE}
        </Alert>
        <pre className="max-h-[26rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800">
          {record.extracted_text}
        </pre>
        <p className="mt-3 text-xs text-slate-500">
          {record.character_count.toLocaleString()} characters read from{" "}
          {record.page_count ?? "?"} {record.page_count === 1 ? "page" : "pages"}.
        </p>
      </>
    );
  }

  if (record.extraction_status === "needs_ocr") {
    return (
      <>
        <Alert tone="warning" title="Text extraction was skipped">
          {OCR_REQUIRED_NOTICE}
        </Alert>
        <p className="mt-3 text-sm text-slate-600">
          The PDF itself is stored and can be viewed or downloaded above. Optical
          character recognition is not available in this phase, so no text is shown
          rather than a guess at what the scan says.
        </p>
      </>
    );
  }

  if (record.extraction_status === "failed") {
    return (
      <>
        <Alert tone="danger" title="Text could not be extracted">
          {record.extraction_error ??
            "CAREVERSE could not read the text out of this file."}
        </Alert>
        <p className="mt-3 text-sm text-slate-600">
          Nothing was lost: the original PDF is stored and can be viewed or
          downloaded above.
          {audience === "patient" && " You can upload it again if it was damaged."}
        </p>
      </>
    );
  }

  // pending / processing
  return (
    <Alert tone="info" title="Text is still being extracted">
      Refresh this page in a moment. The document itself is already stored safely.
    </Alert>
  );
}
