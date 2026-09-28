import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ExtractionBadge from "../../components/ExtractionBadge";
import { documentService } from "../../services/document.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDate, formatDateTime } from "../../utils/format";
import { EXTRACTION_NOTICE, OCR_REQUIRED_NOTICE } from "../../utils/disclaimers";
import type { MedicalDocumentDetail } from "../../types";

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

  const [originalUrl, setOriginalUrl] = useState<string | null>(null);
  const [fileError, setFileError] = useState<string | null>(null);
  const [confirmingDelete, setConfirmingDelete] = useState(false);

  const remove = useMutation({
    mutationFn: () => documentService.remove(documentId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["medical-documents"] });
      navigate("/patient/records");
    },
  });

  // Object URLs are a browser resource, not garbage-collected memory, so
  // they are revoked when this screen goes away rather than left dangling.
  useEffect(() => {
    return () => {
      if (originalUrl) URL.revokeObjectURL(originalUrl);
    };
  }, [originalUrl]);

  const loadOriginal = async (): Promise<string> => {
    if (originalUrl) return originalUrl;
    const blob = await documentService.fetchOriginal(documentId);
    const url = URL.createObjectURL(blob);
    setOriginalUrl(url);
    return url;
  };

  const openOriginal = async () => {
    setFileError(null);
    // Opened synchronously so this still counts as the user's gesture. A
    // tab opened after the `await` would be swallowed by the popup blocker.
    const tab = window.open("", "_blank");
    try {
      const url = await loadOriginal();
      if (tab) {
        tab.location.href = url;
        tab.focus();
      } else {
        setFileError("Your browser blocked the new tab. Use Download instead.");
      }
    } catch (requestError) {
      if (tab) tab.close();
      setFileError(
        getErrorMessage(requestError, "The original document could not be opened."),
      );
    }
  };

  const downloadOriginal = async () => {
    setFileError(null);
    try {
      const url = await loadOriginal();
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = record?.original_filename || `${documentId}.pdf`;
      anchor.click();
    } catch (requestError) {
      setFileError(
        getErrorMessage(requestError, "The document could not be downloaded."),
      );
    }
  };

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
        <Button variant="secondary" size="sm" onClick={openOriginal}>
          View original PDF
        </Button>
        <Button variant="secondary" size="sm" onClick={downloadOriginal}>
          Download
        </Button>
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

      {fileError && (
        <Alert tone="danger" title="The original file is unavailable" className="mb-4">
          {fileError}
        </Alert>
      )}
      {remove.error && (
        <Alert tone="danger" title="The record was not deleted" className="mb-4">
          {getErrorMessage(remove.error, "Please try again.")}
        </Alert>
      )}

      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Document details">
          <dl className="divide-y divide-slate-100 text-sm">
            <Row label="File name" value={record.original_filename} />
            <Row label="Category" value={formatCategory(record.category)} />
            <Row
              label="Date on the document"
              value={record.document_date ? formatDate(record.document_date) : null}
              empty="Not recorded"
            />
            <Row label="Uploaded" value={formatDateTime(record.uploaded_at)} />
            <Row label="Size" value={formatBytes(record.size_bytes)} />
            <Row label="Pages" value={record.page_count} empty="Unknown" />
          </dl>
        </Card>

        <Card title="Extracted text" description="Read out of the PDF automatically.">
          <ExtractionPanel record={record} />
        </Card>
      </div>
    </>
  );
}

function Row({
  label,
  value,
  empty = "-",
}: {
  label: string;
  value: string | number | null | undefined;
  empty?: string;
}) {
  const display =
    value === null || value === undefined || value === "" ? empty : value;
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="truncate text-right font-medium text-slate-900">{display}</dd>
    </div>
  );
}

/**
 * The honest rendering of whatever extraction produced.
 *
 * The non-success states are kept distinct on purpose: a scan we could not
 * read, a file that would not parse, and a document still being processed.
 * Collapsing them into "no text" would tell a patient their report is blank
 * when in fact CAREVERSE never read it.
 */
function ExtractionPanel({ record }: { record: MedicalDocumentDetail }) {
  if (record.extraction_status === "completed" && record.extracted_text) {
    return (
      <>
        <Alert tone="info" className="mb-3">
          {EXTRACTION_NOTICE}
        </Alert>
        <pre className="max-h-[26rem] overflow-auto whitespace-pre-wrap break-words rounded-md border border-slate-200 bg-slate-50 p-4 font-mono text-xs leading-relaxed text-slate-800">
          {record.extracted_text}
        </pre>
        <p className="mt-3 text-xs text-slate-500">
          {record.character_count.toLocaleString()} characters read from{" "}
          {record.page_count ?? "?"} {record.page_count === 1 ? "page" : "pages"}.
        </p>
      </>
    );
  }

  if (record.extraction_status === "needs_ocr") {
    return (
      <>
        <Alert tone="warning" title="Text extraction was skipped">
          {OCR_REQUIRED_NOTICE}
        </Alert>
        <p className="mt-3 text-sm text-slate-600">
          The PDF itself is stored and can be viewed or downloaded above. Optical
          character recognition is not available in this phase, so no text is shown
          rather than a guess at what the scan says.
        </p>
      </>
    );
  }

  if (record.extraction_status === "failed") {
    return (
      <>
        <Alert tone="danger" title="Text could not be extracted">
          {record.extraction_error ??
            "CAREVERSE could not read the text out of this file."}
        </Alert>
        <p className="mt-3 text-sm text-slate-600">
          Nothing was lost: the original PDF is stored and can be viewed or downloaded
          above. You can upload it again if it was damaged.
        </p>
      </>
    );
  }

  // pending / processing
  return (
    <Alert tone="info" title="Text is still being extracted">
      Refresh this page in a moment. The document itself is already stored safely.
    </Alert>
  );
}
