import { Link } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Badge from "../../components/ui/Badge";
import { EXTRACTION_STATUS_LABELS } from "../../utils/disclaimers";

const NEXT_STEPS = [
  {
    title: "Complete your profile",
    body: "Add your date of birth and contact details so your doctor knows whose records they are reading.",
    to: "/patient/profile",
    cta: "Edit profile",
  },
  {
    title: "Upload your medical records",
    body: "Add lab reports, prescriptions or discharge summaries as PDFs. CAREVERSE extracts the text and files it under your profile.",
    to: "/patient/records/upload",
    cta: "Upload a record",
  },
  {
    title: "Authorize your doctor",
    body: "Grant a specific doctor access to your records. Nothing is shared with a doctor until you do this.",
    to: "/patient/profile",
    cta: "Manage access",
  },
];

export default function PatientDashboardPage() {
  const { user } = useAuth();

  return (
    <>
      <PageHeader
        title={`Welcome, ${user?.name ?? "there"}`}
        description="Your uploaded records stay in one profile, and any doctor you authorize sees a summary of them."
      />

      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Records uploaded" description="Shown once you add your first PDF.">
          <p className="text-2xl font-semibold text-slate-900">—</p>
          <p className="mt-1 text-sm text-slate-500">Available in Phase 2</p>
        </Card>
        <Card title="Doctors with access" description="Only doctors you authorize can read your records.">
          <p className="text-2xl font-semibold text-slate-900">—</p>
          <p className="mt-1 text-sm text-slate-500">Available in Phase 3</p>
        </Card>
        <Card title="Extraction health" description="How many uploads were read automatically.">
          <div className="flex flex-wrap gap-1.5 pt-1">
            {Object.entries(EXTRACTION_STATUS_LABELS).map(([status, label]) => (
              <Badge key={status} tone="neutral">
                {label}
              </Badge>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-500">Populated in Phase 2</p>
        </Card>
      </div>

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
                {step.cta} →
              </Link>
            </Card>
          ))}
        </div>
      </section>
    </>
  );
}
