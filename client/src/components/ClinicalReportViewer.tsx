import { useState } from "react";
import Card from "./ui/Card";
import ExtractionBadge from "./ExtractionBadge";
import ExtractionPanel from "./ExtractionPanel";
import DocumentFileActions from "./DocumentFileActions";
import DetailRow from "./DetailRow";
import {
  formatMedicalTestName,
  determineResultStatus,
  getClinicalStatusDetails,
  formatPatientDisplayId,
  formatDocumentDisplayId,
} from "../utils/clinicalFormat";
import { formatBytes, formatCategory, formatDate, formatDateTime } from "../utils/format";
import type { MedicalDocumentDetail } from "../types";

interface LabValueItem {
  name: string;
  value: string;
  unit?: string;
  reference_range?: string;
  flag?: string;
  source_text?: string;
}

interface MedicationItem {
  name: string;
  dosage?: string;
  frequency?: string;
  route?: string;
  source_text?: string;
}

interface StatedConditionItem {
  text: string;
  source_text?: string;
}

interface AnalysisVerdict {
  document_type: string;
  doctor?: string | null;
  facility?: string | null;
  specialty?: string | null;
  observations: string[];
  verdict: string;
}

interface ClinicalReportViewerProps {
  record: MedicalDocumentDetail;
  audience: "patient" | "doctor";
  patientName?: string | null;
  patientCareverseId?: string | null;
  patientId?: string | null;
  fetchOriginal: () => Promise<Blob>;
  actionsSlot?: React.ReactNode;
}

export default function ClinicalReportViewer({
  record,
  audience,
  patientName,
  patientCareverseId,
  patientId,
  fetchOriginal,
  actionsSlot,
}: ClinicalReportViewerProps) {
  const [activeTab, setActiveTab] = useState<"findings" | "raw">("findings");
  const [labFilter, setLabFilter] = useState<"all" | "abnormal">("all");
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const extractedData = (record.extracted_data ?? {}) as {
    lab_values?: LabValueItem[];
    medications?: MedicationItem[];
    stated_conditions?: StatedConditionItem[];
    document_date?: string;
    report_title?: string;
    referring_facility?: string;
    referring_doctor?: string;
    specialty?: string;
    analysis_verdict?: AnalysisVerdict;
  };

  const analysis = extractedData.analysis_verdict;
  const rawLabValues = extractedData.lab_values ?? [];
  const medications = extractedData.medications ?? [];
  const conditions = extractedData.stated_conditions ?? [];

  // Map and interpret lab values with clinical safety
  const labValues = rawLabValues.map((item) => {
    const formattedName = formatMedicalTestName(item.name);
    const clinicalStatus = determineResultStatus(
      item.value,
      item.unit,
      item.reference_range,
      item.flag
    );
    const statusDetails = getClinicalStatusDetails(clinicalStatus);
    return {
      ...item,
      formattedName,
      clinicalStatus,
      statusDetails,
    };
  });

  const abnormalLabCount = labValues.filter(
    (l) => l.clinicalStatus !== "normal" && l.clinicalStatus !== "unavailable"
  ).length;

  const displayedLabs =
    labFilter === "abnormal"
      ? labValues.filter(
          (l) => l.clinicalStatus !== "normal" && l.clinicalStatus !== "unavailable"
        )
      : labValues;

  const displayDocId = formatDocumentDisplayId(record.id, record.document_code);
  const displayPatientId = formatPatientDisplayId(
    patientId || record.patient_id,
    patientCareverseId || record.patient_careverse_id
  );
  const displayPatientName = patientName || record.patient_name;

  const handleCopy = (text: string, type: string) => {
    navigator.clipboard.writeText(text);
    setCopiedId(type);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      {/* 1. Clinical Identification Header Card */}
      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-xs">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="space-y-1">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 border border-teal-200 px-2.5 py-1 rounded-md">
                {displayDocId}
              </span>
              <button
                type="button"
                onClick={() => handleCopy(displayDocId.replace("#", ""), "docId")}
                className="text-xs text-slate-400 hover:text-slate-600 transition-colors"
                title="Copy Document ID"
              >
                {copiedId === "docId" ? "✓ Copied" : "📋 Copy ID"}
              </button>
              <span className="text-slate-300">•</span>
              <span className="font-mono text-xs font-semibold text-slate-700 bg-slate-100 border border-slate-200 px-2 py-1 rounded-md">
                Patient ID: {displayPatientId}
              </span>
              {copiedId === "patId" ? (
                <span className="text-xs text-teal-700 font-medium">✓ Copied</span>
              ) : (
                <button
                  type="button"
                  onClick={() => handleCopy(displayPatientId, "patId")}
                  className="text-xs text-slate-400 hover:text-slate-600"
                  title="Copy Patient ID"
                >
                  📋
                </button>
              )}
            </div>

            <h1 className="text-xl font-bold text-slate-900 tracking-tight sm:text-2xl mt-1">
              {record.title}
            </h1>

            <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500 pt-1">
              {displayPatientName && (
                <>
                  <span className="font-medium text-slate-800">
                    Patient: <strong>{displayPatientName}</strong>
                  </span>
                  <span>•</span>
                </>
              )}
              <span>Category: <strong>{formatCategory(record.category)}</strong></span>
              <span>•</span>
              <span>
                Report Date:{" "}
                <strong>
                  {record.document_date
                    ? formatDate(record.document_date)
                    : extractedData.document_date
                    ? formatDate(extractedData.document_date)
                    : "Not specified on document"}
                </strong>
              </span>
              <span>•</span>
              <span>Uploaded: {formatDateTime(record.uploaded_at)}</span>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 self-start lg:self-auto">
            <ExtractionBadge status={record.extraction_status} />
            <DocumentFileActions
              fetchOriginal={fetchOriginal}
              filename={record.original_filename || `${record.id}.pdf`}
            />
            {actionsSlot}
          </div>
        </div>
      </div>

      {/* 2. Clinical Analysis & Plain-English Verdict Banner */}
      {analysis && (
        <div className="rounded-xl border border-teal-200 bg-gradient-to-br from-teal-50/70 via-white to-slate-50 p-5 shadow-xs">
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-teal-100 pb-3">
            <div className="flex items-center gap-2.5">
              <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-700 text-white font-bold text-base shadow-xs">
                🩺
              </span>
              <div>
                <h2 className="text-sm font-bold text-slate-900 uppercase tracking-wide">
                  Clinical Record Analysis & Patient Verdict
                </h2>
                <p className="text-xs text-slate-500">
                  Automated clinical categorization and clear plain-language takeaways
                </p>
              </div>
            </div>
            <span className="rounded-full bg-teal-100/80 px-3 py-1 text-xs font-semibold text-teal-900 border border-teal-200">
              {analysis.document_type}
            </span>
          </div>

          {/* Plain Takeaway */}
          <div className="mt-4 rounded-lg border border-teal-200/80 bg-white p-4 shadow-2xs">
            <div className="flex items-start gap-3">
              <span className="text-2xl select-none" aria-hidden="true">💡</span>
              <div className="flex-1">
                <h3 className="text-xs font-bold uppercase tracking-wider text-teal-800">
                  {audience === "doctor" ? "Clinical Summary & Stated Content" : "Patient Takeaway in Plain Words"}
                </h3>
                <p className="mt-1 text-sm font-medium leading-relaxed text-slate-800">
                  {analysis.verdict}
                </p>
              </div>
            </div>
          </div>

          {/* Document Observations & Attributed Details */}
          {analysis.observations && analysis.observations.length > 0 && (
            <div className="mt-4">
              <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                Stated Observations & Findings
              </h4>
              <div className="grid gap-2 sm:grid-cols-2">
                {analysis.observations.map((obs, idx) => (
                  <div
                    key={idx}
                    className="flex items-start gap-2 rounded-md border border-slate-200 bg-white p-2.5 text-xs text-slate-700 shadow-2xs"
                  >
                    <span className="text-teal-600 font-bold shrink-0">✓</span>
                    <span className="leading-relaxed">{obs}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* 3. Main Clinical Details Grid */}
      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Metadata & Overview */}
        <div className="space-y-6 lg:col-span-1">
          <Card title="Document Overview">
            <dl className="divide-y divide-slate-100 text-sm">
              <DetailRow label="Document ID" value={displayDocId} />
              <DetailRow label="Patient ID" value={displayPatientId} />
              {displayPatientName && (
                <DetailRow label="Patient Name" value={displayPatientName} />
              )}
              <DetailRow label="File Name" value={record.original_filename} />
              <DetailRow label="Category" value={formatCategory(record.category)} />
              <DetailRow
                label="Date on Document"
                value={
                  record.document_date
                    ? formatDate(record.document_date)
                    : extractedData.document_date
                    ? formatDate(extractedData.document_date)
                    : null
                }
                empty="Not stated on record"
              />
              {(extractedData.referring_facility || analysis?.facility) && (
                <DetailRow
                  label="Healthcare Facility"
                  value={extractedData.referring_facility || analysis?.facility}
                />
              )}
              {(extractedData.referring_doctor || analysis?.doctor) && (
                <DetailRow
                  label="Consulting Doctor"
                  value={extractedData.referring_doctor || analysis?.doctor}
                />
              )}
              {analysis?.specialty && (
                <DetailRow label="Clinical Specialty" value={analysis.specialty} />
              )}
              <DetailRow label="Date Uploaded" value={formatDateTime(record.uploaded_at)} />
              <DetailRow label="File Size" value={formatBytes(record.size_bytes)} />
              <DetailRow label="Pages" value={record.page_count} empty="1 page" />
              <DetailRow
                label="Text Extraction"
                value={
                  record.extraction_status === "completed"
                    ? "Completed successfully"
                    : record.extraction_status === "needs_ocr"
                    ? "Scanned (OCR processed)"
                    : record.extraction_status
                }
              />
            </dl>
          </Card>

          <Card title="Medical Safety & Verification">
            <div className="space-y-3 text-xs leading-relaxed text-slate-600">
              <p>
                This digital view organizes observations and measurements extracted directly from the
                original document.
              </p>
              <div className="rounded-md border border-amber-200 bg-amber-50/70 p-3 text-amber-900">
                <span className="font-semibold block mb-0.5">Clinical Notice:</span>
                Always verify critical values and prescription instructions against the original medical
                document before making clinical decisions.
              </div>
            </div>
          </Card>
        </div>

        {/* Right Column: Structured Findings & Clinical Tables */}
        <div className="space-y-6 lg:col-span-2">
          {/* Section Navigation Tabs */}
          <div className="flex border-b border-slate-200 bg-white rounded-t-xl px-4 pt-2 shadow-2xs">
            <button
              type="button"
              onClick={() => setActiveTab("findings")}
              className={`pb-3 pt-2 px-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === "findings"
                  ? "border-teal-700 text-teal-800"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              📊 Structured Clinical Findings ({labValues.length + medications.length + conditions.length})
            </button>
            <button
              type="button"
              onClick={() => setActiveTab("raw")}
              className={`pb-3 pt-2 px-4 text-sm font-semibold border-b-2 transition-colors ${
                activeTab === "raw"
                  ? "border-teal-700 text-teal-800"
                  : "border-transparent text-slate-500 hover:text-slate-800"
              }`}
            >
              📄 Raw Extracted Text / OCR
            </button>
          </div>

          {activeTab === "findings" && (
            <div className="space-y-6">
              {/* Laboratory Test Results Table */}
              {labValues.length > 0 ? (
                <Card
                  title="🧪 Laboratory Test Results"
                  description="Extracted directly from the verified document. Status is clinically evaluated based on printed reference ranges."
                  actions={
                    abnormalLabCount > 0 ? (
                      <div className="flex items-center gap-1.5 bg-slate-100 p-0.5 rounded-lg text-xs">
                        <button
                          type="button"
                          onClick={() => setLabFilter("all")}
                          className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                            labFilter === "all"
                              ? "bg-white text-slate-900 shadow-2xs"
                              : "text-slate-600 hover:text-slate-900"
                          }`}
                        >
                          All ({labValues.length})
                        </button>
                        <button
                          type="button"
                          onClick={() => setLabFilter("abnormal")}
                          className={`px-2.5 py-1 rounded-md font-medium transition-colors ${
                            labFilter === "abnormal"
                              ? "bg-amber-100 text-amber-900 shadow-2xs"
                              : "text-amber-800 hover:text-amber-900"
                          }`}
                        >
                          Out of Range ({abnormalLabCount})
                        </button>
                      </div>
                    ) : undefined
                  }
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs sm:text-sm border-collapse">
                      <thead>
                        <tr className="border-b border-slate-200 text-slate-500 font-semibold bg-slate-50/50">
                          <th className="py-3 px-3">Test Name</th>
                          <th className="py-3 px-3">Result Value</th>
                          <th className="py-3 px-3">Reference Range</th>
                          <th className="py-3 px-3 text-right sm:text-left">Interpretation</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {displayedLabs.map((item, idx) => (
                          <tr key={idx} className="hover:bg-slate-50/80 transition-colors">
                            {/* Test Name */}
                            <td className="py-3 px-3 align-top font-medium text-slate-900 max-w-[200px] sm:max-w-xs break-words">
                              <div>{item.formattedName}</div>
                              {item.name !== item.formattedName && (
                                <div className="text-[11px] text-slate-400 font-mono mt-0.5">
                                  {item.name}
                                </div>
                              )}
                            </td>

                            {/* Result Value */}
                            <td className="py-3 px-3 align-top font-bold text-slate-900 whitespace-nowrap">
                              <span>{item.value}</span>
                              {item.unit && (
                                <span className="ml-1 text-xs font-normal text-slate-500">
                                  {item.unit}
                                </span>
                              )}
                            </td>

                            {/* Reference Range */}
                            <td className="py-3 px-3 align-top text-slate-600 whitespace-nowrap">
                              {item.reference_range ? (
                                <span>
                                  {item.reference_range} {item.unit || ""}
                                </span>
                              ) : (
                                <span className="text-slate-400">—</span>
                              )}
                            </td>

                            {/* Interpretation Badge */}
                            <td className="py-3 px-3 align-top text-right sm:text-left whitespace-nowrap">
                              <span
                                className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-semibold border ${item.statusDetails.badgeClass}`}
                              >
                                <span
                                  className={`h-1.5 w-1.5 rounded-full ${item.statusDetails.dotClass}`}
                                  aria-hidden="true"
                                />
                                {item.statusDetails.label}
                                {item.flag && !item.statusDetails.label.includes(item.flag) ? (
                                  <span className="text-[10px] opacity-75">({item.flag})</span>
                                ) : null}
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </Card>
              ) : null}

              {/* Prescribed Medications Section */}
              {medications.length > 0 && (
                <Card
                  title="💊 Prescribed Medications"
                  description="Medicines, dosages, and administration instructions detected on this record."
                >
                  <div className="grid gap-3 sm:grid-cols-2">
                    {medications.map((med, idx) => (
                      <div
                        key={idx}
                        className="rounded-lg border border-slate-200 bg-slate-50/70 p-3.5 space-y-1.5"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <h4 className="text-sm font-bold text-slate-900">{med.name}</h4>
                          {med.dosage && (
                            <span className="rounded bg-teal-100 px-2 py-0.5 text-xs font-semibold text-teal-900">
                              {med.dosage}
                            </span>
                          )}
                        </div>

                        {med.frequency && (
                          <p className="text-xs text-slate-600">
                            <strong>Frequency:</strong> {med.frequency}
                          </p>
                        )}
                        {med.route && (
                          <p className="text-xs text-slate-600">
                            <strong>Route:</strong> {med.route}
                          </p>
                        )}
                        {med.source_text && (
                          <p className="text-[11px] text-slate-400 italic pt-1 border-t border-slate-200">
                            &quot;{med.source_text}&quot;
                          </p>
                        )}
                      </div>
                    ))}
                  </div>
                </Card>
              )}

              {/* Stated Conditions & Clinical Notes */}
              {conditions.length > 0 && (
                <Card
                  title="📋 Stated Conditions & Diagnoses"
                  description="Medical conditions explicitly noted in this document."
                >
                  <ul className="divide-y divide-slate-100 text-sm">
                    {conditions.map((cond, idx) => (
                      <li key={idx} className="py-2.5 flex items-start gap-2">
                        <span className="text-teal-600 font-bold">•</span>
                        <span className="text-slate-800 font-medium">{cond.text}</span>
                      </li>
                    ))}
                  </ul>
                </Card>
              )}

              {/* Empty Structured Data Notice */}
              {labValues.length === 0 && medications.length === 0 && conditions.length === 0 && (
                <Card title="Structured Findings">
                  <div className="p-6 text-center text-slate-500">
                    <p className="text-sm">
                      No discrete laboratory tables or prescription items were detected in structured format.
                    </p>
                    <p className="mt-1 text-xs">
                      The document text is fully available under the &quot;Raw Extracted Text / OCR&quot; tab.
                    </p>
                  </div>
                </Card>
              )}
            </div>
          )}

          {activeTab === "raw" && (
            <Card
              title="Raw Extracted Text"
              description="Complete text extracted from the document via OCR. Compare directly against your physical file."
            >
              <ExtractionPanel record={record} audience={audience} />
            </Card>
          )}
        </div>
      </div>
    </div>
  );
}
