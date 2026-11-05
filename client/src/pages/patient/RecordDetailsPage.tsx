import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import ClinicalReportViewer from "../../components/ClinicalReportViewer";
import { documentService } from "../../services/document.service";
import { getErrorCode, getErrorMessage } from "../../services/api";

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
        <Spinner label="Opening your medical report..." />
      </div>
    );
  }

  if (error || !record) {
    const notFound = getErrorCode(error) === "DOCUMENT_NOT_FOUND";
    return (
      <>
        <PageHeader title="Medical Record" />
        <EmptyState
          title={
            notFound
              ? "That record is not available"
              : "This record could not be loaded"
          }
          description={
            notFound
              ? "It may have been deleted, or the link may be outdated. Your records list shows all records you have uploaded."
              : getErrorMessage(error, "Please try again in a moment.")
          }
          action={
            <Link to="/patient/records">
              <Button variant="secondary">Back to Medical Records</Button>
            </Link>
          }
        />
      </>
    );
  }

  return (
    <>
      <div className="mb-4">
        <Link
          to="/patient/records"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 hover:text-teal-900 transition-colors"
        >
          ← Back to All Records
        </Link>
      </div>

      {remove.error && (
        <Alert tone="danger" title="The record was not deleted" className="mb-4">
          {getErrorMessage(remove.error, "Please try again.")}
        </Alert>
      )}

      <ClinicalReportViewer
        record={record}
        audience="patient"
        fetchOriginal={() => documentService.fetchOriginal(documentId)}
        actionsSlot={
          <Button
            variant="danger"
            size="sm"
            onBlur={() => setConfirmingDelete(false)}
            isLoading={remove.isPending}
            onClick={() => {
              if (confirmingDelete) remove.mutate();
              else setConfirmingDelete(true);
            }}
          >
            {confirmingDelete ? "Click to Confirm Delete" : "Delete Record"}
          </Button>
        }
      />
    </>
  );
}
