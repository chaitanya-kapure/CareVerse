import Alert from "./ui/Alert";
import { EXTRACTION_NOTICE, OCR_REQUIRED_NOTICE } from "../utils/disclaimers";
import type { MedicalDocumentDetail } from "../types";

 /** Who is looking at the record. */
export type RecordAudience = "patient" | "doctor";

interface ExtractionPanelProps {
  record: MedicalDocumentDetail;
  audience: RecordAudience;
}

 /** The honest rendering of whatever extraction produced. */
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
        <Alert tone="warning" title="No readable text detected">
          {OCR_REQUIRED_NOTICE}
        </Alert>
        <p className="mt-3 text-sm text-slate-600">
          The document itself is safely preserved and can be viewed or downloaded above. If this
          is a handwritten or low-contrast scan, you can view the original file anytime.
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
