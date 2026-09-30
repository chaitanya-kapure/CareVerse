import { Link, useParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ExtractionBadge from "../../components/ExtractionBadge";
import ExtractionPanel from "../../components/ExtractionPanel";
import DocumentFileActions from "../../components/DocumentFileActions";
import DetailRow from "../../components/DetailRow";
import { doctorService } from "../../services/doctor.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDate, formatDateTime } from "../../utils/format";
import { isWorthRetrying } from "../../utils/query";

/**
 * One record, as an authorized doctor sees it.
 *
 * Deliberately the same components as the patient's own record screen:
 * `ExtractionPanel` renders the extraction state and `DocumentFileActions`
 * opens and downloads the original PDF, both of which are told which audience
 * they are serving. If a report can be read as "extracted text, possibly
 * wrong" by the patient who uploaded it, it has to read that way for the
 * clinician too -- so the copy is shared, not retyped.
 *
 * There is no delete, no replace and no re-upload. The patient owns their
 * records, and a doctor correcting a record is not something this phase
 * allows.
 */
export default function PatientRecordsPage() {
  const { patientId = "", documentId = "" } = useParams();

  const { data: record, isError, isPending, error } = useQuery({
    queryKey: ["doctor-patient-document", patientId, documentId],
    queryFn: () => doctorService.getDocument(patientId, documentId),
    enabled: Boolean(patientId && documentId),
    retry: isWorthRetrying,
  });

  const backToPatient = `/doctor/patients/${patientId}`;

  // See PatientDetailsPage: `isPending` rather than `isLoading`, because a
  // first render is pending-but-idle and would otherwise read as "failed to
  // load" rather than "still loading".
  if (isError || (!record && !isPending)) {
    // Three failures, one screen. A withdrawn grant and a document that
    // belongs to a different patient must not be distinguishable from a
    // document that never existed, so the copy does not commit to a cause.
    const forbidden = getErrorCode(error) === "NO_PATIENT_ACCESS";
    const notFound = getErrorCode(error) === "DOCUMENT_NOT_FOUND";

    return (
      <>
        <PageHeader title="Record" />
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
        <Spinner label="Opening this record" />
      </div>
    );
  }

  return (
    <>
      <PageHeader
        title={record.title}
        description={`${formatCategory(record.category)} - uploaded by the patient on ${formatDateTime(record.uploaded_at)}`}
        actions={<ExtractionBadge status={record.extraction_status} />}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Link to={backToPatient}>
          <Button variant="secondary" size="sm">
            Back to this patient
          </Button>
        </Link>
        <DocumentFileActions
          fetchOriginal={() => doctorService.fetchOriginal(patientId, documentId)}
          filename={record.original_filename || `${documentId}.pdf`}
        />
      </div>

      <Alert tone="info" title="Read-only" className="mb-4">
        You are viewing a record this patient uploaded. CAREVERSE does not edit, correct or
        interpret it &mdash; confirm anything you rely on against the original document and
        with the patient.
      </Alert>

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Document details">
          <dl className="divide-y divide-slate-100 text-sm">
            <DetailRow label="File name" value={record.original_filename} />
            <DetailRow label="Category" value={formatCategory(record.category)} />
            <DetailRow
              label="Date on the document"
              value={record.document_date ? formatDate(record.document_date) : null}
              empty="Not recorded"
            />
            <DetailRow label="Uploaded" value={formatDateTime(record.uploaded_at)} />
            <DetailRow label="Size" value={formatBytes(record.size_bytes)} />
            <DetailRow label="Pages" value={record.page_count} empty="Unknown" />
          </dl>
        </Card>

        <Card title="Extracted text" description="Read out of the PDF automatically.">
          <ExtractionPanel record={record} audience="doctor" />
        </Card>
      </div>
    </>
  );
}
