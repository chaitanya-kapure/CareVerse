import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import EmptyState from "../../components/ui/EmptyState";
import Spinner from "../../components/ui/Spinner";
import ExtractionBadge from "../../components/ExtractionBadge";
import { documentService } from "../../services/document.service";
import { getErrorMessage } from "../../services/api";
import { formatBytes, formatCategory, formatDateTime } from "../../utils/format";

export default function MedicalRecordsPage() {
  const { data, isLoading, error, refetch, isRefetching } = useQuery({
    queryKey: ["medical-documents"],
    queryFn: documentService.list,
  });

  return (
    <>
      <PageHeader
        title="Medical Records"
        description="Every PDF you have uploaded, newest first. Only you can open these."
        actions={
          <Link to="/patient/records/upload">
            <Button variant="primary">Upload a record</Button>
          </Link>
        }
      />

      {error && (
        <Alert tone="danger" title="Your records could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      {isLoading ? (
        <div className="flex min-h-[40vh] items-center justify-center">
          <Spinner label="Loading your records" />
        </div>
      ) : !data || data.items.length === 0 ? (
        <EmptyState
          title="No records yet"
          description="Add a lab report, prescription or discharge summary as a PDF and CAREVERSE will file its text under your profile."
          action={
            <Link to="/patient/records/upload">
              <Button>Upload your first record</Button>
            </Link>
          }
        />
      ) : (
        <>
          <p className="mb-3 text-sm text-slate-500">
            {data.total} {data.total === 1 ? "record" : "records"}
            {isRefetching ? " - refreshing" : ""}
          </p>

          <ul className="divide-y divide-slate-200 rounded-lg border border-slate-200 bg-white shadow-sm">
            {data.items.map((doc) => (
              <li key={doc.id}>
                <Link
                  to={`/patient/records/${doc.id}`}
                  className="flex flex-wrap items-center justify-between gap-3 px-5 py-4 transition-colors hover:bg-slate-50"
                >
                  <div className="min-w-0">
                    <p className="truncate text-sm font-medium text-slate-900">
                      {doc.title}
                    </p>
                    <p className="mt-0.5 truncate text-xs text-slate-500">
                      {doc.original_filename}
                      <span aria-hidden="true"> - </span>
                      {formatCategory(doc.category)}
                      <span aria-hidden="true"> - </span>
                      uploaded {formatDateTime(doc.uploaded_at)}
                      <span aria-hidden="true"> - </span>
                      {formatBytes(doc.size_bytes)}
                    </p>
                  </div>
                  <ExtractionBadge status={doc.extraction_status} />
                </Link>
              </li>
            ))}
          </ul>

          <div className="mt-4">
            <Button variant="secondary" size="sm" onClick={() => refetch()} isLoading={isRefetching}>
              Refresh
            </Button>
          </div>
        </>
      )}
    </>
  );
}
