import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import { useAuth } from "../../hooks/useAuth";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Badge from "../../components/ui/Badge";
import { doctorService } from "../../services/doctor.service";
import { getErrorMessage } from "../../services/api";
import { isWorthRetrying } from "../../utils/query";

/**
 * Doctor Dashboard — clinical command center.
 * Provides authorized patient counts, direct lookup by CareVerse ID, and access governance summary.
 */
export default function DoctorDashboardPage() {
  const { user } = useAuth();

  const { data, isPending, error } = useQuery({
    queryKey: ["doctor-patients"],
    queryFn: doctorService.listPatients,
    retry: isWorthRetrying,
  });

  const total = data?.total ?? 0;
  const records = data?.items.reduce((sum, entry) => sum + entry.document_count, 0) ?? 0;

  return (
    <>
      <PageHeader
        title={`Welcome, Dr. ${user?.name ?? ""}`.trim()}
        description="Clinical Dashboard. Review authorized patient records, find patients by CareVerse ID, and inspect digitized reports."
        actions={
          <div className="flex items-center gap-2">
            <Link to="/doctor/find-patient">
              <Button size="sm">+ Find Patient by ID</Button>
            </Link>
          </div>
        }
      />

      {error && (
        <Alert tone="danger" title="Your patient list could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      {/* Quick Action Clinical Banner */}
      <div className="mb-6 rounded-xl border border-teal-200 bg-gradient-to-r from-teal-50/70 via-white to-slate-50 p-4 shadow-2xs">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-teal-700 text-white font-bold text-lg shadow-xs">
              🔍
            </span>
            <div>
              <h3 className="text-sm font-bold text-slate-900">
                Patient Direct Lookup (CareVerse ID)
              </h3>
              <p className="text-xs text-slate-500">
                Have a patient present in clinic? Enter their 4-digit CareVerse ID to request or verify record access.
              </p>
            </div>
          </div>
          <Link to="/doctor/find-patient" className="shrink-0">
            <Button variant="secondary" size="sm">
              Open Patient Lookup →
            </Button>
          </Link>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Authorized Patients"
          description="Patients who have granted clinical access to their health records."
        >
          <div className="flex items-baseline gap-3">
            <p className="text-3xl font-extrabold text-slate-900">
              {isPending ? "-" : total}
            </p>
            <span className="text-xs font-semibold uppercase tracking-wider text-teal-800 bg-teal-50 border border-teal-200 px-2.5 py-0.5 rounded-full">
              {total === 1 ? "Active Patient" : "Active Patients"}
            </span>
          </div>

          <p className="mt-2 text-sm text-slate-600">
            {isPending
              ? "Loading authorized patient registry..."
              : total === 0
                ? "No patients have granted access yet. Patients can authorize your profile using your name or specialty."
                : `Viewing ${records} medical ${records === 1 ? "document" : "documents"} across your authorized patient caseload.`}
          </p>

          <div className="mt-4 pt-3 border-t border-slate-100 flex items-center justify-between">
            <Link
              to="/doctor/patients"
              className="text-sm font-semibold text-teal-700 hover:text-teal-900 transition-colors"
            >
              Open Authorized Patient List →
            </Link>
            <Link
              to="/doctor/profile"
              className="text-xs font-medium text-slate-500 hover:text-slate-800"
            >
              Update Clinician Profile
            </Link>
          </div>
        </Card>

        <Card title="Clinical Access & Safety Governance" description="CareVerse zero-trust healthcare model.">
          <ul className="space-y-2.5 text-xs text-slate-600">
            <li className="flex items-start gap-2">
              <Badge tone="success">Consent-First</Badge>
              <span>Access is explicitly granted by patients. There is no open or unconsented patient directory.</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge tone="info">Document ID</Badge>
              <span>Each medical report is assigned an immutable Document ID for audit trail traceability.</span>
            </li>
            <li className="flex items-start gap-2">
              <Badge tone="warning">Clinical Review</Badge>
              <span>
                Extracted test values and OCR readings should always be verified against the original medical file.
              </span>
            </li>
            <li className="flex items-start gap-2">
              <Badge tone="neutral">Read-Only</Badge>
              <span>
                Clinicians possess read-only record access. Patient documents cannot be edited or overwritten.
              </span>
            </li>
          </ul>
        </Card>
      </div>

      {total > 0 && (
        <div className="mt-6 flex items-center gap-3">
          <Link to="/doctor/patients">
            <Button>View Authorized Patient Records</Button>
          </Link>
          <Link to="/doctor/find-patient">
            <Button variant="secondary">Look up by CareVerse ID</Button>
          </Link>
        </div>
      )}
    </>
  );
}
