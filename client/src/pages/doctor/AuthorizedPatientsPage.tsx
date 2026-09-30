import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import { doctorService } from "../../services/doctor.service";
import { getErrorMessage } from "../../services/api";
import { formatDate, formatGender } from "../../utils/format";
import { isWorthRetrying } from "../../utils/query";

/**
 * The doctor side of `patient_access`, and nothing else.
 *
 * There is no search box, no filter and no page of "all patients" behind a
 * failed one. The only ids that can reach this screen are the ones the server
 * already decided this doctor may read, so there is nothing here that could
 * turn into a patient directory. That is a deliberate limitation: CAREVERSE
 * has no way to look up a patient you are not already authorized for.
 */
export default function AuthorizedPatientsPage() {
  // `isPending`, not `isLoading`: on the first render a React Query
  // observation is pending but not yet fetching, so an `isLoading` guard
  // briefly falls through and shows "no patients have authorized you" --
  // a false, alarming answer to someone who in fact has several.
  const { data, isPending, error, refetch, isRefetching } = useQuery({
    queryKey: ["doctor-patients"],
    queryFn: doctorService.listPatients,
    retry: isWorthRetrying,
  });

  return (
    <>
      <PageHeader
        title="Authorized Patients"
        description="Patients who have granted you access to their records. No one appears here until they do."
        actions={
          <Button variant="secondary" size="sm" onClick={() => refetch()} isLoading={isRefetching}>
            Refresh
          </Button>
        }
      />

      {error && (
        <Alert tone="danger" title="Your patient list could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      {isPending ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner label="Loading your authorized patients" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No patients have authorized you yet"
          description="Access is granted by the patient from their own account. There is no way to search for a patient or request access, so this list stays empty until someone names you specifically."
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-500">
            {data.total} authorized {data.total === 1 ? "patient" : "patients"}
          </p>

          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white shadow-sm">
            {data.items.map((entry) => (
              <li key={entry.patient_id}>
                <Link
                  to={`/doctor/patients/${entry.patient_id}`}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {entry.full_name}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {entry.date_of_birth ? formatDate(entry.date_of_birth) : "Date of birth not recorded"}
                      <span aria-hidden="true"> &middot; </span>
                      {formatGender(entry.gender)}
                      <span aria-hidden="true"> &middot; </span>
                      {entry.document_count}{" "}
                      {entry.document_count === 1 ? "record" : "records"}
                    </p>
                  </div>
                  {entry.document_count === 0 ? (
                    <Badge tone="neutral">No records uploaded</Badge>
                  ) : null}
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}

      <Card className="mt-6" title="What you can do here">
        <p className="text-sm leading-relaxed text-slate-600">
          Open a patient to read their profile and records, view the original PDF, and read
          any text CAREVERSE extracted from it. You cannot edit, replace or delete a
          patient&apos;s records &mdash; the patient remains the owner of everything they
          have uploaded, and they can revoke your access at any time.
        </p>
      </Card>
    </>
  );
}
