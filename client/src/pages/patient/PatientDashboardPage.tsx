import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import ExtractionBadge from "../../components/ExtractionBadge";
import { documentService } from "../../services/document.service";
import type { ExtractionStatus } from "../../types";

const NEXT_STEPS = [
  {
    title: "Complete your profile",
    body: "Add your date of birth and contact details so a record is identifiable as yours.",
    to: "/patient/profile",
    cta: "Edit profile",
  },
  {
    title: "Upload a medical record",
    body: "Add a lab report, prescription or discharge summary as a PDF. CAREVERSE stores the file and extracts its text.",
    to: "/patient/records/upload",
    cta: "Upload a record",
  },
  {
    title: "Authorize a doctor",
    body: "Grant one specific doctor access to your records. Nothing is shared with anyone until you do this.",
    to: "/patient/profile",
    cta: "Manage access",
  },
];

export default function PatientDashboardPage() {
  const { user } = useAuth();

  // Same query the records list uses, so the number here and the number
  // there come from one cache entry rather than two requests that can
  // disagree.
  const { data, isLoading } = useQuery({
    queryKey: ["medical-documents"],
    queryFn: documentService.list,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;

  // "Completed" is the only outcome where text was actually read. Anything
  // else is worth the patient knowing about without them having to open
  // every record to find out.
  const unreadable = items.filter(
    (doc) => doc.extraction_status === "needs_ocr" || doc.extraction_status === "failed",
  ).length;
  const extracted = items.filter((doc) => doc.extraction_status === "completed").length;

  const statusCounts = items.reduce<Record<ExtractionStatus, number>>(
    (counts, doc) => {
      counts[doc.extraction_status] = (counts[doc.extraction_status] ?? 0) + 1;
      return counts;
    },
    { pending: 0, processing: 0, completed: 0, needs_ocr: 0, failed: 0 },
  );

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.name ?? "there"}`}
        description="Your uploaded records stay under your profile, and no one else can read them."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Records uploaded" description="Everything filed under your profile.">
          <p className="text-2xl font-semibold text-slate-900">
            {isLoading ? "-" : total}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {total === 0 ? "Upload your first PDF to get started" : "Newest first in your records"}
          </p>
        </Card>

        <Card
          title="Text extracted"
          description="Records where the PDF had readable text."
        >
          <p className="text-2xl font-semibold text-slate-900">
            {isLoading ? "-" : extracted}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {unreadable > 0
              ? `${unreadable} ${unreadable === 1 ? "record" : "records"} could not be read automatically`
              : "Scanned documents are reported separately"}
          </p>
        </Card>

        <Card title="Doctors with access" description="Only doctors you authorize.">
          <p className="text-2xl font-semibold text-slate-900">-</p>
          <p className="mt-1 text-sm text-slate-500">Available in Phase 3</p>
        </Card>
      </div>

      {total > 0 && (
        <section aria-labelledby="extraction-health" className="mt-8">
          <h2 id="extraction-health" className="text-base font-semibold text-slate-900">
            Extraction status
          </h2>
          <div className="mt-3 flex flex-wrap items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm">
            {(
              [
                ["completed", "Extracted"],
                ["needs_ocr", "Needs OCR"],
                ["failed", "Extraction failed"],
                ["processing", "Processing"],
                ["pending", "Queued"],
              ] as Array<[ExtractionStatus, string]>
            )
              .filter(([status]) => statusCounts[status] > 0)
              .map(([status, label]) => (
                <span key={status} className="inline-flex items-center gap-1.5 text-sm">
                  <ExtractionBadge status={status} />
                  <span className="text-slate-600">
                    {statusCounts[status]} {label.toLowerCase()}
                  </span>
                </span>
              ))}
            {unreadable > 0 && (
              <Link
                to="/patient/records"
                className="ml-auto text-sm font-medium text-teal-700 hover:underline"
              >
                Review them
              </Link>
            )}
          </div>
        </section>
      )}

      <section aria-labelledby="next-steps" className="mt-8">
        <h2 id="next-steps" className="text-base font-semibold text-slate-900">
          Get started
        </h2>
        <div className="mt-4 grid gap-4 md:grid-cols-3">
          {NEXT_STEPS.map((step) => (
            <Card key={step.title}>
              <h3 className="font-medium text-slate-900">{step.title}</h3>
              <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{step.body}</p>
              <Link
                to={step.to}
                className="mt-3 inline-block text-sm font-medium text-teal-700 hover:underline"
              >
                {step.cta} -&gt;
              </Link>
            </Card>
          ))}
        </div>
      </section>

      <div className="mt-8">
        <Link to="/patient/records">
          <Button variant="secondary">Go to medical records</Button>
        </Link>
      </div>
    </>
  );
}
