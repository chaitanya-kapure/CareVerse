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
import { formatPatientDisplayId } from "../../utils/clinicalFormat";
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
  const { data, isPending, error, refetch, isRefetching } = useQuery({
    queryKey: ["doctor-patients"],
    queryFn: doctorService.listPatients,
    retry: isWorthRetrying,
  });

  return (
    <>
      <PageHeader
        title="Authorized Patients"
        description="Patients who have granted you access to their medical records. No one appears here until authorized."
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
          description="Access is granted by the patient from their own account. There is no open patient directory; patients explicitly authorize your clinical profile."
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-500">
            {data.total} authorized {data.total === 1 ? "patient" : "patients"}
          </p>

          <ul className="divide-y divide-slate-200 rounded-xl border border-slate-200 bg-white shadow-xs overflow-hidden">
            {data.items.map((entry) => {
              const displayPatientId = formatPatientDisplayId(entry.patient_id, entry.careverse_id);
              return (
                <li key={entry.patient_id}>
                  <Link
                    to={`/doctor/patients/${entry.patient_id}`}
                    className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="font-mono text-xs font-bold text-teal-800 bg-teal-50 border border-teal-200 px-2.5 py-0.5 rounded">
                          {displayPatientId}
                        </span>
                        <p className="truncate text-sm font-semibold text-slate-900 hover:text-teal-700">
                          {entry.full_name}
                        </p>
                      </div>
                      <p className="mt-1 truncate text-xs text-slate-500">
                        {entry.date_of_birth ? formatDate(entry.date_of_birth) : "Date of birth not recorded"}
                        <span aria-hidden="true"> &middot; </span>
                        {formatGender(entry.gender)}
                        <span aria-hidden="true"> &middot; </span>
                        <span className="font-medium text-slate-700">
                          {entry.document_count} {entry.document_count === 1 ? "record" : "records"}
                        </span>
                      </p>
                    </div>

                    <div className="flex items-center gap-3">
                      {entry.document_count === 0 ? (
                        <Badge tone="neutral">No records uploaded</Badge>
                      ) : (
                        <span className="text-xs font-semibold text-teal-700">Open records →</span>
                      )}
                    </div>
                  </Link>
                </li>
              );
            })}
          </ul>
        </>
      )}

      <Card className="mt-6" title="Clinical Governance & Privacy">
        <p className="text-sm leading-relaxed text-slate-600">
          Access covers only patients who have explicitly granted authorization. Every access request
          and record viewing session is strictly audited under healthcare privacy compliance guidelines.
        </p>
      </Card>
    </>
  );
}
