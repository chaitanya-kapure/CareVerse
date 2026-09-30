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
 * A summary of the authorized list, not a second copy of it.
 *
 * The full list lives one click away; repeating it here would mean two
 * screens that have to agree about who is authorized, and this one is the
 * screen a doctor lands on. It answers a single question -- do I have anyone
 * to look at -- and points at the list.
 *
 * The query key is the same one `AuthorizedPatientsPage` uses, so both screens
 * read one cache entry and cannot disagree about the count.
 */
export default function DoctorDashboardPage() {
  const { user } = useAuth();

  // `isPending`, not `isLoading` -- see AuthorizedPatientsPage. The
  // distinction matters here too: reading a first render as "0 patients"
  // would tell a doctor with a full caseload that nobody has authorized them.
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
        description="You only see patients who have explicitly authorized you. Records are never shared automatically."
      />

      {error && (
        <Alert tone="danger" title="Your patient list could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      <div className="grid gap-4 md:grid-cols-2">
        <Card
          title="Authorized patients"
          description="Patients who have granted you access to their records."
        >
          <p className="text-2xl font-semibold text-slate-900">
            {isPending ? "-" : total}
          </p>
          <p className="mt-1 text-sm text-slate-500">
            {isPending
              ? "Loading your list"
              : total === 0
                ? "No patient has authorized you yet"
                : `Viewing ${records} ${records === 1 ? "record" : "records"} across your authorized patients`}
          </p>
          {total > 0 && (
            <Link
              to="/doctor/patients"
              className="mt-3 inline-block text-sm font-medium text-teal-700 hover:underline"
            >
              Open your patient list -&gt;
            </Link>
          )}
        </Card>

        <Card title="How access works" description="CAREVERSE authorization model.">
          <ul className="space-y-2 text-sm text-slate-600">
            <li className="flex gap-2">
              <Badge tone="success">Consent</Badge>
              <span>A patient grants access from their own profile. There is no open patient directory.</span>
            </li>
            <li className="flex gap-2">
              <Badge tone="info">Scoped</Badge>
              <span>Access covers only that one patient, and the patient can revoke it at any time.</span>
            </li>
            <li className="flex gap-2">
              <Badge tone="warning">Verify</Badge>
              <span>
                Extracted text is read automatically and can be misread. Always confirm values
                against the original PDF.
              </span>
            </li>
            <li className="flex gap-2">
              <Badge tone="neutral">Read only</Badge>
              <span>
                You can read a patient&apos;s records. You cannot upload, edit or delete them.
              </span>
            </li>
          </ul>
        </Card>
      </div>

      {total === 0 && !isPending && !error && (
        <div className="mt-6">
          <Alert tone="info" title="Nothing to show yet">
            CAREVERSE has no way to find a patient on your behalf. A patient has to authorize
            you from their own account first, and until they do there is no record here for you
            to open &mdash; not a filtered-out one.
          </Alert>
        </div>
      )}

      {total > 0 && (
        <div className="mt-6">
          <Link to="/doctor/patients">
            <Button>View authorized patients</Button>
          </Link>
        </div>
      )}
    </>
  );
}
