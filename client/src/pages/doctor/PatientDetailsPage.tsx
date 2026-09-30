import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import DetailRow from "../../components/DetailRow";
import ExtractionBadge from "../../components/ExtractionBadge";
import { doctorService } from "../../services/doctor.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDate, formatDateTime, formatGender } from "../../utils/format";
import { isWorthRetrying } from "../../utils/query";
import { NOT_A_DIAGNOSIS_READER_NOTICE } from "../../utils/disclaimers";

/**
 * One authorized patient: their profile, and the records they have uploaded.
 *
 * The `patientId` in the URL is attacker-controlled input as far as the
 * browser is concerned, and this screen passes it straight through. That is
 * safe only because the server authorizes it on every request -- if the grant
 * is not there, both queries below come back refused and the screen says so
 * without revealing whether the id names a real patient.
 *
 * Nothing here writes. The patient owns their records; a doctor is a reader.
 */
export default function PatientDetailsPage() {
  const { patientId = "" } = useParams();

  const profile = useQuery({
    queryKey: ["doctor-patient", patientId],
    queryFn: () => doctorService.getPatient(patientId),
    enabled: Boolean(patientId),
    retry: isWorthRetrying,
  });

  const documents = useQuery({
    queryKey: ["doctor-patient-documents", patientId],
    queryFn: () => doctorService.listDocuments(patientId),
    enabled: Boolean(patientId),
    retry: isWorthRetrying,
  });

  // The grant was withdrawn, or never existed. Both are the same answer, and
  // the screen must not imply which one it was.
  if (profile.isError || documents.isError) {
    const forbidden =
      getErrorCode(profile.error) === "NO_PATIENT_ACCESS" ||
      getErrorCode(documents.error) === "NO_PATIENT_ACCESS";

    return (
      <>
        <PageHeader title="Patient" />
        <EmptyState
          title={
            forbidden
              ? "You do not have access to this patient"
              : "This patient could not be loaded"
          }
          description={
            forbidden
              ? "A patient has to authorize you before their profile or records become available. This is the same response whether or not an account exists with that id."
              : getErrorMessage(profile.error ?? documents.error, "Please try again in a moment.")
          }
          action={
            <Link to="/doctor/patients">
              <Button variant="secondary">Back to authorized patients</Button>
            </Link>
          }
        />
      </>
    );
  }

  // `isPending`, not `isLoading`. `isLoading` is only true once the request
  // is *also* in flight, and on the very first render a React Query
  // observation is pending but idle -- so an `isLoading` guard falls straight
  // through to the success path and renders a screen full of "not recorded"
  // for a patient who simply has not loaded yet. Checking the error state
  // first, then the pending state, leaves no gap between the two.
  if (profile.isPending || documents.isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Loading this patient's records" />
      </div>
    );
  }

  const patient = profile.data;
  const records = documents.data?.items ?? [];

  return (
    <>
      <PageHeader
        title={patient?.full_name ?? "Patient"}
        description="Records this patient has uploaded. Read-only — the patient owns and controls everything here."
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Link to="/doctor/patients">
          <Button variant="secondary" size="sm">
            Back to authorized patients
          </Button>
        </Link>
      </div>

      <Alert tone="info" title="Records as uploaded" className="mb-4">
        {NOT_A_DIAGNOSIS_READER_NOTICE}
      </Alert>

      <div className="grid gap-4 lg:grid-cols-3">
        <Card
          title="Patient profile"
          description="The details the patient entered themselves."
          className="lg:col-span-1"
        >
          <dl className="divide-y divide-slate-100 text-sm">
            <DetailRow label="Full name" value={patient?.full_name} empty="Not provided" />
            <DetailRow
              label="Date of birth"
              value={patient?.date_of_birth ? formatDate(patient.date_of_birth) : null}
              empty="Not recorded"
            />
            <DetailRow label="Gender" value={formatGender(patient?.gender)} />
            <DetailRow label="Phone" value={patient?.phone} empty="Not recorded" />
            <DetailRow label="Address" value={patient?.address} empty="Not recorded" />
          </dl>
          {patient?.notes && (
            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50 p-3">
              <p className="text-xs font-medium uppercase tracking-wide text-slate-500">
                In the patient&apos;s own words
              </p>
              <p className="mt-1 whitespace-pre-wrap text-sm text-slate-700">{patient.notes}</p>
            </div>
          )}
        </Card>

        <Card
          title="Medical records"
          description="Every PDF this patient has uploaded, newest first."
          className="lg:col-span-2"
        >
          {records.length === 0 ? (
            <EmptyState
              title="No records uploaded"
              description="This patient has not uploaded any documents yet. There is nothing to read, and nothing CAREVERSE has failed to read."
            />
          ) : (
            <ul className="divide-y divide-slate-200">
              {records.map((doc) => (
                <li key={doc.id}>
                  <Link
                    to={`/doctor/patients/${patientId}/records/${doc.id}`}
                    className="-mx-2 flex flex-wrap items-center justify-between gap-3 rounded-md px-2 py-3 transition-colors hover:bg-slate-50"
                  >
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium text-slate-900">{doc.title}</p>
                      <p className="mt-0.5 truncate text-xs text-slate-500">
                        {doc.original_filename}
                        <span aria-hidden="true"> &middot; </span>
                        {formatCategory(doc.category)}
                        <span aria-hidden="true"> &middot; </span>
                        {doc.document_date
                          ? `dated ${formatDate(doc.document_date)}`
                          : "no date on document"}
                        <span aria-hidden="true"> &middot; </span>
                        uploaded {formatDateTime(doc.uploaded_at)}
                        <span aria-hidden="true"> &middot; </span>
                        {formatBytes(doc.size_bytes)}
                      </p>
                    </div>
                    <ExtractionBadge status={doc.extraction_status} />
                  </Link>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
    </>
  );
}
