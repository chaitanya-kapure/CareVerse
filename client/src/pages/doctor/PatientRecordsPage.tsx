import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ClinicalReportViewer from "../../components/ClinicalReportViewer";
import { doctorService } from "../../services/doctor.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { isWorthRetrying } from "../../utils/query";

/**
 * One patient record, as an authorized doctor sees it.
 *
 * Utilizes the same ClinicalReportViewer component as the patient screen to ensure
 * unified clinical fidelity: human-readable test names, distinct abnormal/normal status
 * pills, structured lab tables, medications, and raw text verification.
 */
export default function PatientRecordsPage() {
  const { patientId = "", documentId = "" } = useParams();

  const { data: record, isError, isPending, error } = useQuery({
    queryKey: ["doctor-patient-document", patientId, documentId],
    queryFn: () => doctorService.getDocument(patientId, documentId),
    enabled: Boolean(patientId && documentId),
    retry: isWorthRetrying,
  });

  const { data: patient } = useQuery({
    queryKey: ["doctor-patient", patientId],
    queryFn: () => doctorService.getPatient(patientId),
    enabled: Boolean(patientId),
  });

  const backToPatient = `/doctor/patients/${patientId}`;

  if (isError || (!record && !isPending)) {
    const forbidden = getErrorCode(error) === "NO_PATIENT_ACCESS";
    const notFound = getErrorCode(error) === "DOCUMENT_NOT_FOUND";

    return (
      <>
        <PageHeader title="Patient Medical Record" />
        <EmptyState
          title={
            forbidden
              ? "You do not have access to this record"
              : notFound
                ? "That record is not available"
                : "This record could not be loaded"
          }
          description={
            forbidden
              ? "A patient has to authorize you before their records become available."
              : notFound
                ? "It may have been deleted, or the link may be out of date."
                : getErrorMessage(error, "Please try again in a moment.")
          }
          action={
            <Link to={backToPatient}>
              <Button variant="secondary">Back to this patient</Button>
            </Link>
          }
        />
      </>
    );
  }

  if (isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Opening this patient report..." />
      </div>
    );
  }

  return (
    <>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <Link
          to={backToPatient}
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 hover:text-teal-900 transition-colors"
        >
          ← Back to Patient Profile &amp; Records
        </Link>
        <Link to={`/doctor/patients/${patientId}/summary`}>
          <Button variant="secondary" size="sm">
            View Patient AI Summary
          </Button>
        </Link>
      </div>

      <Alert tone="info" title="Clinical Read-Only Access" className="mb-4">
        You are reviewing a medical document uploaded by the patient. CAREVERSE digitizes and
        organizes observations as printed on the document. Always verify critical findings and
        dosages against the original document.
      </Alert>

      <ClinicalReportViewer
        record={record}
        audience="doctor"
        patientId={patientId}
        patientName={patient?.full_name}
        patientCareverseId={patient?.careverse_id}
        fetchOriginal={() => doctorService.fetchOriginal(patientId, documentId)}
      />
    </>
  );
}
