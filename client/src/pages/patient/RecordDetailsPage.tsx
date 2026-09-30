import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

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
import { documentService } from "../../services/document.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDate, formatDateTime } from "../../utils/format";

/**
 * One record: what it is, what CAREVERSE managed to read out of it, and the
 * controls over it.
 *
 * The extracted text is always presented as *extracted* -- never as a
 * finding. Every status other than `completed` is stated plainly, because a
 * patient must be able to tell "we could not read this" apart from "this
 * document says nothing".
 *
 * The fetched record is called `record` rather than `document` throughout:
 * `document` is the DOM global, and shadowing it in a component that also
 * creates anchor elements is a trap that costs a confusing type error.
 */
export default function RecordDetailsPage() {
  const { documentId = "" } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const {
    data: record,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["medical-document", documentId],
    queryFn: () => documentService.get(documentId),
    enabled: Boolean(documentId),
  });

  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const remove = useMutation({
    mutationFn: () => documentService.remove(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["medical-documents"] });
      navigate("/patient/records");
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Opening your record" />
      </div>
    );
  }

  // A missing document and one belonging to somebody else are the same
  // answer here, by design -- telling them apart would confirm that a given
  // id exists.
  if (error || !record) {
    const notFound = getErrorCode(error) === "DOCUMENT_NOT_FOUND";
    return (
      <>
        <PageHeader title="Record" />
        <EmptyState
          title={
            notFound
              ? "That record is not available"
              : "This record could not be loaded"
          }
          description={
            notFound
              ? "It may have been deleted, or the link may be out of date. Your list shows everything you have uploaded."
              : getErrorMessage(error, "Please try again in a moment.")
          }
          action={
            <Link to="/patient/records">
              <Button variant="secondary">Back to medical records</Button>
            </Link>
          }
        />
      </>
    );
  }

  return (
    <>
      <PageHeader
        title={record.title}
        description={`${formatCategory(record.category)} - uploaded ${formatDateTime(record.uploaded_at)}`}
        actions={<ExtractionBadge status={record.extraction_status} />}
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Link to="/patient/records">
          <Button variant="secondary" size="sm">
            Back to records
          </Button>
        </Link>
        <DocumentFileActions
          fetchOriginal={() => documentService.fetchOriginal(documentId)}
          filename={record.original_filename || `${documentId}.pdf`}
        />
        <span className="flex-1" />
        <Button
          variant="danger"
          size="sm"
          onBlur={() => setConfirmingDelete(false)}
          isLoading={remove.isPending}
          onClick={() => {
            // Two clicks, not a modal: the destructive action stays visible
            // and keyboard-reachable, and a stray click cannot delete a
            // record.
            if (confirmingDelete) remove.mutate();
            else setConfirmingDelete(true);
          }}
        >
          {confirmingDelete ? "Click again to confirm" : "Delete"}
        </Button>
      </div>

      {remove.error && (
        <Alert tone="danger" title="The record was not deleted" className="mb-4">
          {getErrorMessage(remove.error, "Please try again.")}
        </Alert>
      )}

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
          <ExtractionPanel record={record} audience="patient" />
        </Card>
      </div>
    </>
  );
}
