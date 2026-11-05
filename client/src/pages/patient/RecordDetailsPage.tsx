import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ExtractionBadge from "../../components/ExtractionBadge";
import ExtractionPanel from "../../components/ExtractionPanel";
import DocumentFileActions from "../../components/DocumentFileActions";
import DetailRow from "../../components/DetailRow";
import { documentService } from "../../services/document.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDate, formatDateTime } from "../../utils/format";

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

export default function RecordDetailsPage() {
  const { documentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: record,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["medical-document", documentId],
    queryFn: () => documentService.get(documentId),
    enabled: Boolean(documentId),
  });

  const [confirmingDelete, setConfirmingDelete] = useState(false);
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"highlights" | "raw">("highlights");

  const remove = useMutation({
    mutationFn: () => documentService.remove(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["medical-documents"] });
      navigate("/patient/records");
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Opening your medical record..." />
      </div>
    );
  }

  if (error || !record) {
    const notFound = getErrorCode(error) === "DOCUMENT_NOT_FOUND";
    return (
      <>
        <PageHeader title="Medical Record" />
        <EmptyState
          title={
            notFound
              ? "That record is not available"
              : "This record could not be loaded"
          }
          description={
            notFound
              ? "It may have been deleted, or the link may be outdated. Your list shows all records you have uploaded."
              : getErrorMessage(error, "Please try again in a moment.")
          }
          action={
            <Link to="/patient/records">
              <Button variant="secondary">Back to Medical Records</Button>
            </Link>
          }
        />
      </>
    );
  }

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
  const labValues = extractedData.lab_values ?? [];
  const medications = extractedData.medications ?? [];
  const conditions = extractedData.stated_conditions ?? [];
  const hasStructuredInsights =
    labValues.length > 0 || medications.length > 0 || conditions.length > 0;

  const handleCopyText = () => {
    if (record.extracted_text) {
      navigator.clipboard.writeText(record.extracted_text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <>
      <div className="mb-2">
        <Link
          to="/patient/records"
          className="inline-flex items-center gap-1 text-sm font-medium text-teal-700 hover:text-teal-800"
        >
          ← Back to All Records
        </Link>
      </div>

      <PageHeader
        title={record.title}
        description={`${formatCategory(record.category)} • Uploaded on ${formatDateTime(record.uploaded_at)}`}
        actions={
          <div className="flex items-center gap-2">
            <ExtractionBadge status={record.extraction_status} />
          </div>
        }
      />

      {/* Top Action Bar */}
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
        <div className="flex flex-wrap items-center gap-2">
          <DocumentFileActions
            fetchOriginal={() => documentService.fetchOriginal(documentId)}
            filename={record.original_filename || `${documentId}.pdf`}
          />
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="danger"
            size="sm"
            onBlur={() => setConfirmingDelete(false)}
            isLoading={remove.isPending}
            onClick={() => {
              if (confirmingDelete) remove.mutate();
              else setConfirmingDelete(true);
            }}
          >
            {confirmingDelete ? "Click to Confirm Delete" : "Delete Record"}
          </Button>
        </div>
      </div>

      {remove.error && (
        <Alert tone="danger" title="The record was not deleted" className="mb-4">
          {getErrorMessage(remove.error, "Please try again.")}
        </Alert>
      )}

      {/* Main Grid */}
      <div className="space-y-6">
        {/* Prominent Clinical Analysis & Patient Verdict Banner */}
        {analysis && (
          <div className="rounded-xl border border-teal-200 bg-gradient-to-r from-teal-50/90 via-white to-teal-50/50 p-5 shadow-sm">
            <div className="flex flex-wrap items-center justify-between gap-3 border-b border-teal-100 pb-3">
              <div className="flex items-center gap-2.5">
                <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-teal-700 text-white font-bold text-base shadow-xs">
                  🩺
                </span>
                <div>
                  <h2 className="text-base font-bold text-slate-900">
                    Clinical Analysis & Patient Verdict
                  </h2>
                  <p className="text-xs text-slate-500">
                    Automated review and plain-English summary of your uploaded document
                  </p>
                </div>
              </div>
              <span className="rounded-full bg-teal-100 px-3 py-1 text-xs font-semibold text-teal-800">
                {analysis.document_type}
              </span>
            </div>

            {/* Verdict Box */}
            <div className="mt-4 rounded-lg border border-teal-200 bg-white p-4 shadow-xs">
              <div className="flex items-start gap-3">
                <span className="text-2xl">💡</span>
                <div className="flex-1">
                  <h3 className="text-xs font-bold uppercase tracking-wider text-teal-800">
                    Patient Takeaway in Simple Words
                  </h3>
                  <p className="mt-1 text-sm font-medium leading-relaxed text-slate-800">
                    {analysis.verdict}
                  </p>
                </div>
              </div>
            </div>

            {/* Key Observations List */}
            {analysis.observations && analysis.observations.length > 0 && (
              <div className="mt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Document Observations & Stated Details
                </h4>
                <div className="grid gap-2 sm:grid-cols-2">
                  {analysis.observations.map((obs, idx) => (
                    <div
                      key={idx}
                      className="flex items-start gap-2 rounded-md border border-teal-100 bg-white/90 p-2.5 text-xs text-slate-700"
                    >
                      <span className="text-teal-600 font-bold shrink-0">✓</span>
                      <span>{obs}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}

        <div className="grid gap-6 lg:grid-cols-3">
          {/* Left Column: Metadata & Overview */}
          <div className="space-y-6 lg:col-span-1">
            <Card title="Document Details">
              <dl className="divide-y divide-slate-100 text-sm">
                <DetailRow label="Original File" value={record.original_filename} />
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
                    label="Hospital / Facility"
                    value={extractedData.referring_facility || analysis?.facility}
                  />
                )}
                {(extractedData.referring_doctor || analysis?.doctor) && (
                  <DetailRow
                    label="Doctor / Signee"
                    value={extractedData.referring_doctor || analysis?.doctor}
                  />
                )}
                {analysis?.specialty && (
                  <DetailRow label="Specialty" value={analysis.specialty} />
                )}
                <DetailRow label="Uploaded On" value={formatDateTime(record.uploaded_at)} />
                <DetailRow label="File Size" value={formatBytes(record.size_bytes)} />
                <DetailRow label="Page Count" value={record.page_count} empty="1 page" />
                <DetailRow
                  label="Text Extraction"
                  value={
                    record.extraction_status === "completed"
                      ? "Completed successfully"
                      : record.extraction_status === "needs_ocr"
                      ? "Scanned (No text found)"
                      : record.extraction_status
                  }
                />
              </dl>
            </Card>

            <Card title="Quick Actions">
              <p className="text-xs text-slate-500 mb-3">
                Include this in your health timeline or share with your doctor:
              </p>
              <div className="flex flex-col gap-2">
                <Link to="/patient/summary">
                  <Button variant="secondary" size="sm" className="w-full justify-center">
                    View in AI Health Summary
                  </Button>
                </Link>
                <Link to="/patient/discover">
                  <Button variant="secondary" size="sm" className="w-full justify-center">
                    Share with a Doctor
                  </Button>
                </Link>
              </div>
            </Card>
          </div>

          {/* Right Column: Extracted Content Tabs */}
          <div className="space-y-6 lg:col-span-2">
            {/* Tab Selection */}
            <div className="flex border-b border-slate-200 bg-white rounded-t-lg px-4 pt-2">
              <button
                type="button"
                onClick={() => setActiveTab("highlights")}
                className={`pb-3 pt-2 px-4 text-sm font-semibold border-b-2 transition-colors ${
                  activeTab === "highlights"
                    ? "border-teal-700 text-teal-800"
                    : "border-transparent text-slate-500 hover:text-slate-800"
                }`}
              >
                📊 Structured Findings {hasStructuredInsights && `(${labValues.length + medications.length + conditions.length})`}
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
                📄 Raw Extracted Text / OCR Output
              </button>
            </div>

            {activeTab === "highlights" && (
              <div className="space-y-6">
                {/* Lab Values Table */}
                {labValues.length > 0 && (
                  <Card
                    title="🧪 Laboratory Test Results"
                    description="Extracted directly from the document. Flags are transcribed as printed."
                  >
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs sm:text-sm">
                        <thead>
                          <tr className="border-b border-slate-200 text-slate-500 font-medium">
                            <th className="py-2.5 pr-4">Test Name</th>
                            <th className="py-2.5 px-3">Result</th>
                            <th className="py-2.5 px-3">Reference Range</th>
                            <th className="py-2.5 pl-3">Status</th>
                          </tr>
                        </thead>
                        <tbody className="divide-y divide-slate-100">
                          {labValues.map((item, idx) => {
                            const isHigh =
                              item.flag?.toLowerCase().includes("h") ||
                              item.flag?.toLowerCase().includes("high");
                            const isLow =
                              item.flag?.toLowerCase().includes("l") ||
                              item.flag?.toLowerCase().includes("low");

                            return (
                              <tr key={idx} className="hover:bg-slate-50">
                                <td className="py-2.5 pr-4 font-medium text-slate-900">
                                  {item.name}
                                </td>
                                <td className="py-2.5 px-3 font-semibold text-slate-800">
                                  {item.value} {item.unit || ""}
                                </td>
                                <td className="py-2.5 px-3 text-slate-500">
                                  {item.reference_range || "—"}
                                </td>
                                <td className="py-2.5 pl-3">
                                  {isHigh ? (
                                    <span className="inline-flex items-center rounded-full bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-800">
                                      High ({item.flag})
                                    </span>
                                  ) : isLow ? (
                                    <span className="inline-flex items-center rounded-full bg-blue-100 px-2 py-0.5 text-xs font-semibold text-blue-800">
                                      Low ({item.flag})
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                                      Normal
                                    </span>
                                  )}
                                </td>
                              </tr>
                            );
                          })}
                        </tbody>
                      </table>
                    </div>
                  </Card>
                )}

                {/* Medications List */}
                {medications.length > 0 && (
                  <Card
                    title="💊 Prescribed Medications"
                    description="Medicines and dosages detected in this prescription or report."
                  >
                    <div className="grid gap-3 sm:grid-cols-2">
                      {medications.map((med, idx) => (
                        <div
                          key={idx}
                          className="rounded-lg border border-slate-200 bg-slate-50 p-3"
                        >
                          <p className="font-semibold text-slate-900">{med.name}</p>
                          <p className="mt-1 text-xs text-slate-600">
                            {med.dosage && <span className="font-medium">{med.dosage} </span>}
                            {med.frequency && <span>• {med.frequency}</span>}
                            {med.route && <span>• {med.route}</span>}
                          </p>
                        </div>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Stated Conditions */}
                {conditions.length > 0 && (
                  <Card
                    title="🩺 Medical Conditions & Diagnoses"
                    description="Explicit medical diagnoses or conditions stated in the text."
                  >
                    <div className="flex flex-wrap gap-2">
                      {conditions.map((cond, idx) => (
                        <span
                          key={idx}
                          className="rounded-md bg-teal-50 border border-teal-200 px-3 py-1.5 text-xs font-medium text-teal-900"
                        >
                          {cond.text}
                        </span>
                      ))}
                    </div>
                  </Card>
                )}

                {/* Extracted Text view when no numeric tables exist */}
                {!hasStructuredInsights && (
                  <Card
                    title="Scanned Document Text"
                    description={`OCR scanner recognized ${record.character_count} characters.`}
                    actions={
                      record.extracted_text ? (
                        <Button variant="secondary" size="sm" onClick={handleCopyText}>
                          {copied ? "✓ Copied!" : "Copy Text"}
                        </Button>
                      ) : undefined
                    }
                  >
                    <ExtractionPanel record={record} audience="patient" />
                  </Card>
                )}
              </div>
            )}

            {activeTab === "raw" && (
              <Card
                title="Complete Extracted Content"
                description="Verbatim text extracted automatically via OCR scanner."
                actions={
                  record.extracted_text ? (
                    <Button variant="secondary" size="sm" onClick={handleCopyText}>
                      {copied ? "✓ Copied!" : "Copy Text"}
                    </Button>
                  ) : undefined
                }
              >
                <ExtractionPanel record={record} audience="patient" />
              </Card>
            )}
          </div>
        </div>
      </div>
    </>
  );
}
