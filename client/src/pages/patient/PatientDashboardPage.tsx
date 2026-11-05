import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import ExtractionBadge from "../../components/ExtractionBadge";
import { documentService } from "../../services/document.service";
import { accessService } from "../../services/access.service";
import { formatBytes, formatCategory, formatDateTime } from "../../utils/format";
import type { ExtractionStatus } from "../../types";

export default function PatientDashboardPage() {
  const { user } = useAuth();
  const [showDismissibleGuide, setShowDismissibleGuide] = useState(true);

  const { data, isLoading } = useQuery({
    queryKey: ["medical-documents"],
    queryFn: documentService.list,
  });

  const { data: access } = useQuery({
    queryKey: ["patient-access"],
    queryFn: accessService.list,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const activeGrants = (access?.items ?? []).filter((entry) => entry.status === "active").length;

  const extracted = items.filter((doc) => doc.extraction_status === "completed").length;
  const unreadable = items.filter(
    (doc) => doc.extraction_status === "needs_ocr" || doc.extraction_status === "failed",
  ).length;

  const statusCounts = items.reduce<Record<ExtractionStatus, number>>(
    (counts, doc) => {
      counts[doc.extraction_status] = (counts[doc.extraction_status] ?? 0) + 1;
      return counts;
    },
    { pending: 0, processing: 0, completed: 0, needs_ocr: 0, failed: 0 },
  );

  const recentDocs = items.slice(0, 4);

  return (
    <div className="space-y-6">
      <PageHeader
        title={`Welcome, ${user?.name ?? "there"} 👋`}
        description="Your central digital health vault. Securely store medical documents, extract clinical facts with OCR, and access your AI health summary."
        actions={
          <Link to="/patient/records/upload">
            <Button size="lg" className="shadow-sm">
              + Upload Medical Record
            </Button>
          </Link>
        }
      />

      {/* First-Time User Onboarding / Welcome Guide */}
      {showDismissibleGuide && (
        <div className="relative overflow-hidden rounded-xl border border-teal-200 bg-gradient-to-r from-teal-50 via-teal-50/50 to-white p-5 shadow-sm">
          <div className="flex items-start justify-between gap-4">
            <div>
              <span className="inline-flex items-center gap-1.5 rounded-full bg-teal-100 px-2.5 py-0.5 text-xs font-semibold text-teal-800">
                🚀 Getting Started with CareVerse
              </span>
              <h2 className="mt-2 text-base font-semibold text-slate-900 sm:text-lg">
                How CareVerse Works in 3 Simple Steps
              </h2>
              <p className="mt-1 text-xs text-slate-600 sm:text-sm">
                Easily organize your health history and get an instant AI summary to share with your doctor.
              </p>
            </div>
            <button
              type="button"
              onClick={() => setShowDismissibleGuide(false)}
              className="text-xs font-medium text-slate-400 hover:text-slate-600"
              title="Dismiss guide"
            >
              ✕ Dismiss
            </button>
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-3">
            <div className="rounded-lg border border-teal-100 bg-white p-3.5 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                  1
                </span>
                <h3 className="font-semibold text-xs sm:text-sm text-slate-900">
                  Upload Documents
                </h3>
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                Add PDFs or photos of lab tests, prescriptions, and hospital discharge notes.
              </p>
              <Link
                to="/patient/records/upload"
                className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
              >
                Upload now →
              </Link>
            </div>

            <div className="rounded-lg border border-teal-100 bg-white p-3.5 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                  2
                </span>
                <h3 className="font-semibold text-xs sm:text-sm text-slate-900">
                  Automatic OCR Scan
                </h3>
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                Our engine reads scanned text, extracting blood values, medications, and dates.
              </p>
              <Link
                to="/patient/records"
                className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
              >
                View records →
              </Link>
            </div>

            <div className="rounded-lg border border-teal-100 bg-white p-3.5 shadow-sm">
              <div className="flex items-center gap-2">
                <span className="flex h-6 w-6 items-center justify-center rounded-full bg-teal-700 text-xs font-bold text-white">
                  3
                </span>
                <h3 className="font-semibold text-xs sm:text-sm text-slate-900">
                  AI Summary & Sharing
                </h3>
              </div>
              <p className="mt-1.5 text-xs text-slate-600 leading-relaxed">
                Review your consolidated health summary and securely authorize doctors to view it.
              </p>
              <Link
                to="/patient/summary"
                className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
              >
                Check summary →
              </Link>
            </div>
          </div>
        </div>
      )}

      {/* Quick Action Bar */}
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-4">
        <Link
          to="/patient/records/upload"
          className="flex items-center gap-3 rounded-xl border border-teal-200 bg-teal-50/60 p-4 transition-all hover:bg-teal-100/70 hover:shadow-sm"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-teal-700 text-white font-bold text-lg">
            +
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Upload Record</p>
            <p className="text-xs text-slate-500">PDFs or Camera Photos</p>
          </div>
        </Link>

        <Link
          to="/patient/records"
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-slate-300 hover:shadow-sm"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-blue-50 text-blue-700 font-bold text-lg">
            📋
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">My Records</p>
            <p className="text-xs text-slate-500">{total} filed documents</p>
          </div>
        </Link>

        <Link
          to="/patient/summary"
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-slate-300 hover:shadow-sm"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-purple-50 text-purple-700 font-bold text-lg">
            🧠
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Health Summary</p>
            <p className="text-xs text-slate-500">AI-assisted overview</p>
          </div>
        </Link>

        <Link
          to="/patient/discover"
          className="flex items-center gap-3 rounded-xl border border-slate-200 bg-white p-4 transition-all hover:border-slate-300 hover:shadow-sm"
        >
          <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg bg-emerald-50 text-emerald-700 font-bold text-lg">
            👨‍⚕️
          </div>
          <div>
            <p className="text-sm font-semibold text-slate-900">Find Doctors</p>
            <p className="text-xs text-slate-500">Discover and grant access</p>
          </div>
        </Link>
      </div>

      {/* Vital Stats Cards */}
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Total Records Filed" description="Stored safely under your private account.">
          <div className="flex items-baseline justify-between">
            <p className="text-3xl font-bold text-slate-900">
              {isLoading ? "-" : total}
            </p>
            <span className="text-xs font-medium text-teal-700">
              {total === 0 ? "Empty vault" : "100% encrypted"}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {total === 0
              ? "Upload your first prescription or test result"
              : "Lab tests, prescriptions, and summaries"}
          </p>
        </Card>

        <Card
          title="OCR & Extracted Records"
          description="Documents analyzed for clinical data."
        >
          <div className="flex items-baseline justify-between">
            <p className="text-3xl font-bold text-teal-700">
              {isLoading ? "-" : extracted}
            </p>
            <span className="text-xs font-medium text-slate-500">
              {total > 0 ? `${Math.round((extracted / total) * 100)}% analyzed` : "0%"}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {unreadable > 0
              ? `${unreadable} document${unreadable === 1 ? "" : "s"} had no legible text`
              : "All readable documents are ready for summary"}
          </p>
        </Card>

        <Card title="Authorized Doctors" description="Clinicians with permission to read your history.">
          <div className="flex items-baseline justify-between">
            <p className="text-3xl font-bold text-slate-900">
              {access ? activeGrants : "-"}
            </p>
            <span className="text-xs font-medium text-slate-500">
              {activeGrants > 0 ? "Active sharing" : "Private only"}
            </span>
          </div>
          <p className="mt-2 text-xs text-slate-500">
            {activeGrants === 0
              ? "No doctor can see your records until you grant access"
              : "You can revoke doctor access at any time"}
          </p>
        </Card>
      </div>

      {/* Extraction Health Strip */}
      {total > 0 && (
        <section aria-labelledby="extraction-health">
          <div className="flex flex-wrap items-center justify-between gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
                Document Status:
              </span>
              {(
                [
                  ["completed", "Extracted"],
                  ["needs_ocr", "Needs OCR"],
                  ["failed", "Failed"],
                  ["processing", "Processing"],
                  ["pending", "Queued"],
                ] as Array<[ExtractionStatus, string]>
              )
                .filter(([status]) => statusCounts[status] > 0)
                .map(([status, label]) => (
                  <span key={status} className="inline-flex items-center gap-1.5 text-xs font-medium">
                    <ExtractionBadge status={status} />
                    <span className="text-slate-600">
                      {statusCounts[status]} {label.toLowerCase()}
                    </span>
                  </span>
                ))}
            </div>
            <Link
              to="/patient/records"
              className="text-xs font-semibold text-teal-700 hover:underline"
            >
              View all records →
            </Link>
          </div>
        </section>
      )}

      {/* Recent Medical Records Preview */}
      <section aria-labelledby="recent-records">
        <div className="flex items-center justify-between">
          <h2 id="recent-records" className="text-base font-semibold text-slate-900">
            Recent Medical Records
          </h2>
          {total > 0 && (
            <Link
              to="/patient/records"
              className="text-xs font-semibold text-teal-700 hover:underline"
            >
              View all ({total}) →
            </Link>
          )}
        </div>

        {total === 0 ? (
          <div className="mt-3 rounded-xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-slate-100 text-slate-400 text-xl">
              📂
            </div>
            <h3 className="mt-3 text-sm font-semibold text-slate-900">No records uploaded yet</h3>
            <p className="mt-1 text-xs text-slate-500 max-w-sm mx-auto">
              Add your lab reports, prescriptions, or discharge summaries. PDF documents and camera photos are supported.
            </p>
            <div className="mt-4">
              <Link to="/patient/records/upload">
                <Button size="sm">+ Upload Your First Record</Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="mt-3 divide-y divide-slate-100 rounded-xl border border-slate-200 bg-white shadow-sm overflow-hidden">
            {recentDocs.map((doc) => (
              <div
                key={doc.id}
                className="flex flex-wrap items-center justify-between gap-3 p-4 transition-colors hover:bg-slate-50/80"
              >
                <div className="min-w-0 flex-1">
                  <Link
                    to={`/patient/records/${doc.id}`}
                    className="truncate text-sm font-semibold text-slate-900 hover:text-teal-700 block"
                  >
                    {doc.title}
                  </Link>
                  <p className="mt-0.5 truncate text-xs text-slate-500">
                    <span className="font-medium text-slate-700">{formatCategory(doc.category)}</span>
                    <span aria-hidden="true"> • </span>
                    Uploaded {formatDateTime(doc.uploaded_at)}
                    <span aria-hidden="true"> • </span>
                    {formatBytes(doc.size_bytes)}
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  <ExtractionBadge status={doc.extraction_status} />
                  <Link to={`/patient/records/${doc.id}`}>
                    <Button variant="secondary" size="sm">
                      View Details
                    </Button>
                  </Link>
                </div>
              </div>
            ))}
          </div>
        )}
      </section>

      {/* Helpful Account Checklist */}
      <section aria-labelledby="checklist" className="mt-6">
        <h2 id="checklist" className="text-base font-semibold text-slate-900 mb-3">
          Profile & Security Tips
        </h2>
        <div className="grid gap-4 md:grid-cols-2">
          <Card>
            <div className="flex items-start gap-3">
              <span className="text-xl">👤</span>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Complete Your Health Profile</h3>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  Ensure your Date of Birth and gender are up to date so your clinical summary matches your identity.
                </p>
                <Link
                  to="/patient/profile"
                  className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
                >
                  Manage Profile →
                </Link>
              </div>
            </div>
          </Card>

          <Card>
            <div className="flex items-start gap-3">
              <span className="text-xl">🔒</span>
              <div>
                <h3 className="text-sm font-semibold text-slate-900">Doctor Access Control</h3>
                <p className="mt-1 text-xs text-slate-600 leading-relaxed">
                  You are in full control of who reads your documents. Share records with your verified doctors or revoke access anytime.
                </p>
                <Link
                  to="/patient/discover"
                  className="mt-2 inline-block text-xs font-semibold text-teal-700 hover:underline"
                >
                  Discover & Authorize Doctors →
                </Link>
              </div>
            </div>
          </Card>
        </div>
      </section>
    </div>
  );
}
