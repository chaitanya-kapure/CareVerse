import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import { accessRequestService } from "../../services/access-request.service";
import { getErrorMessage } from "../../services/api";
import { formatDateTime } from "../../utils/format";
import type { AccessRequest, AccessRequestStatus } from "../../types";

function RequestBadge({ status }: { status: AccessRequestStatus }) {
  switch (status) {
    case "approved":
      return <Badge tone="success">Approved</Badge>;
    case "rejected":
      return <Badge tone="danger">Rejected</Badge>;
    case "pending":
      return <Badge tone="warning">Pending Approval</Badge>;
    case "revoked":
      return <Badge tone="neutral">Revoked</Badge>;
    case "expired":
      return <Badge tone="neutral">Expired</Badge>;
    default:
      return <Badge tone="neutral">{status}</Badge>;
  }
}

interface RequestCardProps {
  request: AccessRequest;
  onApprove: (id: string) => void;
  onReject: (id: string, reason?: string) => void;
  isActionPending: boolean;
}

function PendingRequestCard({
  request,
  onApprove,
  onReject,
  isActionPending,
}: RequestCardProps) {
  const [showRejectForm, setShowRejectForm] = useState(false);
  const [rejectReason, setRejectReason] = useState("");
  const [confirmingApprove, setConfirmingApprove] = useState(false);

  return (
    <div className="rounded-lg border-2 border-amber-300 bg-amber-50/40 p-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h4 className="text-base font-bold text-slate-900">{request.doctor_name}</h4>
            <RequestBadge status={request.status} />
          </div>
          <p className="mt-1 text-sm font-medium text-slate-800">
            Purpose: <span className="font-normal text-slate-700">{request.purpose}</span>
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-600">
            <span>Requested Duration: <strong className="text-slate-800">{request.requested_duration_days} days</strong></span>
            {request.requested_categories && request.requested_categories.length > 0 && (
              <span>Categories: <strong className="text-slate-800">{request.requested_categories.join(", ")}</strong></span>
            )}
            <span>Received: {formatDateTime(request.created_at)}</span>
          </div>
        </div>

        {!showRejectForm && (
          <div className="flex items-center gap-2">
            {confirmingApprove ? (
              <div className="flex items-center gap-2">
                <Button
                  size="sm"
                  variant="primary"
                  isLoading={isActionPending}
                  onClick={() => onApprove(request.id)}
                >
                  Confirm Grant
                </Button>
                <Button
                  size="sm"
                  variant="secondary"
                  onClick={() => setConfirmingApprove(false)}
                >
                  Cancel
                </Button>
              </div>
            ) : (
              <Button
                size="sm"
                variant="primary"
                onClick={() => setConfirmingApprove(true)}
              >
                Approve Access
              </Button>
            )}

            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setConfirmingApprove(false);
                setShowRejectForm(true);
              }}
            >
              Reject
            </Button>
          </div>
        )}
      </div>

      {showRejectForm && (
        <div className="mt-4 border-t border-amber-200/80 pt-3">
          <label htmlFor={`reject-reason-${request.id}`} className="block text-xs font-medium text-slate-700 mb-1">
            Reason for rejection (optional):
          </label>
          <div className="flex flex-col sm:flex-row gap-2">
            <input
              id={`reject-reason-${request.id}`}
              type="text"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              placeholder="e.g. Not my current primary physician, wrong doctor."
              className="flex-1 rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-red-500 focus:outline-none focus:ring-1 focus:ring-red-500"
            />
            <div className="flex items-center gap-2">
              <Button
                size="sm"
                variant="danger"
                isLoading={isActionPending}
                onClick={() => onReject(request.id, rejectReason.trim() || undefined)}
              >
                Confirm Rejection
              </Button>
              <Button
                size="sm"
                variant="secondary"
                onClick={() => {
                  setShowRejectForm(false);
                  setRejectReason("");
                }}
              >
                Cancel
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AccessRequestsPage() {
  const queryClient = useQueryClient();

  const { data, isLoading, error } = useQuery({
    queryKey: ["access-requests-received"],
    queryFn: () => accessRequestService.listReceived(),
  });

  const approveMutation = useMutation({
    mutationFn: (requestId: string) => accessRequestService.approve(requestId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["access-requests-received"] });
      queryClient.invalidateQueries({ queryKey: ["patient-access"] });
    },
  });

  const rejectMutation = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason?: string }) =>
      accessRequestService.reject(id, reason),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["access-requests-received"] });
    },
  });

  const isActionPending = approveMutation.isPending || rejectMutation.isPending;

  const requests = data?.items ?? [];
  const pendingRequests = requests.filter((r) => r.status === "pending");
  const pastRequests = requests.filter((r) => r.status !== "pending");

  return (
    <>
      <PageHeader
        title="Record Access Requests"
        description="Review requests from clinicians asking to view your medical records and health history."
      />

      {approveMutation.error && (
        <Alert tone="danger" className="mb-4">
          {getErrorMessage(approveMutation.error, "Could not approve access request.")}
        </Alert>
      )}

      {rejectMutation.error && (
        <Alert tone="danger" className="mb-4">
          {getErrorMessage(rejectMutation.error, "Could not reject access request.")}
        </Alert>
      )}

      {isLoading ? (
        <div className="py-12">
          <Spinner label="Loading access requests" />
        </div>
      ) : error ? (
        <Alert tone="danger" title="Could not load access requests">
          {getErrorMessage(error, "Please try again later.")}
        </Alert>
      ) : (
        <div className="space-y-6">
          {pendingRequests.length > 0 && (
            <Card
              title={`Pending Requests (${pendingRequests.length})`}
              description="Doctors waiting for your permission to read your documents."
            >
              <div className="space-y-3">
                {pendingRequests.map((req) => (
                  <PendingRequestCard
                    key={req.id}
                    request={req}
                    onApprove={(id) => approveMutation.mutate(id)}
                    onReject={(id, reason) => rejectMutation.mutate({ id, reason })}
                    isActionPending={isActionPending}
                  />
                ))}
              </div>
            </Card>
          )}

          <Card
            title="Past & Resolved Requests"
            description="History of previous requests and decisions."
          >
            {pastRequests.length === 0 ? (
              <EmptyState
                title="No past requests"
                description="Your past decisions and access history will appear here."
              />
            ) : (
              <div className="divide-y divide-slate-200">
                {pastRequests.map((req) => (
                  <div key={req.id} className="py-3.5 first:pt-0 last:pb-0">
                    <div className="flex flex-wrap items-start justify-between gap-2">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-slate-900">{req.doctor_name}</span>
                          <RequestBadge status={req.status} />
                        </div>
                        <p className="mt-1 text-sm text-slate-700">Purpose: {req.purpose}</p>
                        <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-slate-500">
                          <span>Duration: {req.requested_duration_days} days</span>
                          {req.requested_categories && req.requested_categories.length > 0 && (
                            <span>Categories: {req.requested_categories.join(", ")}</span>
                          )}
                          <span>Requested: {formatDateTime(req.created_at)}</span>
                          {req.responded_at && (
                            <span>Resolved: {formatDateTime(req.responded_at)}</span>
                          )}
                        </div>
                        {req.status === "rejected" && req.rejection_reason && (
                          <p className="mt-1 text-xs text-red-600 bg-red-50 rounded p-1.5 inline-block">
                            Rejection note: {req.rejection_reason}
                          </p>
                        )}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
