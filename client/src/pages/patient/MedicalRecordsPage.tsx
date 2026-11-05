import { useState, useMemo } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import ExtractionBadge from "../../components/ExtractionBadge";
import { documentService } from "../../services/document.service";
import { getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDateTime } from "../../utils/format";
import { formatDocumentDisplayId } from "../../utils/clinicalFormat";

const CATEGORY_FILTERS = [
  { value: "all", label: "All Records" },
  { value: "lab_report", label: "🧪 Lab Reports" },
  { value: "prescription", label: "💊 Prescriptions" },
  { value: "discharge_summary", label: "🏥 Discharge Summaries" },
  { value: "imaging", label: "🩻 Imaging Reports" },
  { value: "other", label: "📄 Other" },
];

export default function MedicalRecordsPage() {
  const [searchTerm, setSearchTerm] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("all");

  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ["medical-documents"],
    queryFn: documentService.list,
  });

  const allItems = data?.items ?? [];

  const filteredItems = useMemo(() => {
    return allItems.filter((doc) => {
      const matchesCategory =
        selectedCategory === "all" || doc.category === selectedCategory;
      const docCode = formatDocumentDisplayId(doc.id, doc.document_code);
      const matchesSearch =
        searchTerm.trim() === "" ||
        doc.title.toLowerCase().includes(searchTerm.toLowerCase()) ||
        doc.original_filename.toLowerCase().includes(searchTerm.toLowerCase()) ||
        docCode.toLowerCase().includes(searchTerm.toLowerCase());
      return matchesCategory && matchesSearch;
    });
  }, [allItems, selectedCategory, searchTerm]);

  return (
    <>
      <PageHeader
        title="Medical Records"
        description="Every medical report, test result, and prescription filed under your profile. Click any record to inspect test results and OCR text."
        actions={
          <Link to="/patient/records/upload">
            <Button size="lg">+ Upload a Record</Button>
          </Link>
        }
      />

      {error && (
        <Alert tone="danger" title="Your records could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      {isLoading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner label="Loading your records..." />
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No records uploaded yet"
          description="Upload your lab reports, prescriptions, or discharge summaries as PDFs or photos. CareVerse automatically organizes them and extracts medical data."
          action={
            <Link to="/patient/records/upload">
              <Button>Upload your first record</Button>
            </Link>
          }
        />
      ) : (
        <div className="space-y-4">
          {/* Search & Category Filter Bar */}
          <div className="flex flex-col gap-3 rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:flex-row sm:items-center sm:justify-between">
            <div className="relative flex-1">
              <input
                type="text"
                placeholder="Search by title, document ID, or file name..."
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
                className="w-full rounded-lg border border-slate-300 py-2 pl-3 pr-8 text-sm focus:border-teal-700 focus:outline-none focus:ring-1 focus:ring-teal-700"
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm("")}
                  className="absolute right-2.5 top-2.5 text-xs text-slate-400 hover:text-slate-600"
                >
                  ✕
                </button>
              )}
            </div>

            <div className="flex flex-wrap gap-1.5">
              {CATEGORY_FILTERS.map((cat) => (
                <button
                  key={cat.value}
                  type="button"
                  onClick={() => setSelectedCategory(cat.value)}
                  className={`rounded-full px-3 py-1 text-xs font-semibold transition-colors ${
                    selectedCategory === cat.value
                      ? "bg-teal-700 text-white shadow-sm"
                      : "bg-slate-100 text-slate-600 hover:bg-slate-200"
                  }`}
                >
                  {cat.label}
                </button>
              ))}
            </div>
          </div>

          <div className="flex items-center justify-between text-xs text-slate-500 px-1">
            <p>
              Showing <strong>{filteredItems.length}</strong> of {data.total}{" "}
              {data.total === 1 ? "record" : "records"}
              {isRefetching ? " • refreshing..." : ""}
            </p>
            <button
              type="button"
              onClick={() => refetch()}
              className="font-medium text-teal-700 hover:underline"
            >
              ↻ Refresh list
            </button>
          </div>

          {filteredItems.length === 0 ? (
            <div className="rounded-xl border border-slate-200 bg-white p-8 text-center">
              <p className="text-sm font-semibold text-slate-900">No matching records found</p>
              <p className="mt-1 text-xs text-slate-500">
                Try adjusting your search terms or category filter.
              </p>
              <Button
                variant="secondary"
                size="sm"
                className="mt-3"
                onClick={() => {
                  setSearchTerm("");
                  setSelectedCategory("all");
                }}
              >
                Clear Filters
              </Button>
            </div>
          ) : (
            <ul className="divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
              {filteredItems.map((doc) => {
                const docCode = formatDocumentDisplayId(doc.id, doc.document_code);
                return (
                  <li key={doc.id}>
                    <Link
                      to={`/patient/records/${doc.id}`}
                      className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-slate-50"
                    >
                      <div className="min-w-0 flex-1">
                        <div className="flex flex-wrap items-center gap-2">
                          <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 border border-teal-200 px-2 py-0.5 rounded">
                            {docCode}
                          </span>
                          <p className="truncate text-sm font-semibold text-slate-900 hover:text-teal-700">
                            {doc.title}
                          </p>
                        </div>
                        <p className="mt-1.5 truncate text-xs text-slate-500">
                          <span className="font-medium text-slate-700">
                            {formatCategory(doc.category)}
                          </span>
                          <span aria-hidden="true"> • </span>
                          {doc.original_filename}
                          <span aria-hidden="true"> • </span>
                          Uploaded {formatDateTime(doc.uploaded_at)}
                          <span aria-hidden="true"> • </span>
                          {formatBytes(doc.size_bytes)}
                        </p>
                      </div>

                      <div className="flex items-center gap-3">
                        <ExtractionBadge status={doc.extraction_status} />
                        <span className="text-xs font-semibold text-teal-700">View Report →</span>
                      </div>
                    </Link>
                  </li>
                );
              })}
            </ul>
          )}
        </div>
      )}
    </>
  );
}
