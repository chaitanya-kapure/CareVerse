import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import { Textarea } from "../../components/ui/Field";
import { doctorProfileService } from "../../services/doctor-profile.service";
import { accessRequestService } from "../../services/access-request.service";
import { getErrorMessage } from "../../services/api";
import { formatDateTime } from "../../utils/format";
import type { AccessRequestStatus, PatientDiscoveryResult } from "../../types";

const CATEGORIES = [
  "General Records",
  "Lab Reports",
  "Prescriptions",
  "Discharge Summaries",
  "Imaging Reports",
  "All Records",
];

const DURATION_OPTIONS = [
  { days: 7, label: "7 days" },
  { days: 30, label: "30 days" },
  { days: 90, label: "90 days" },
  { days: 180, label: "180 days" },
  { days: 365, label: "1 year (365 days)" },
];

function RequestStatusBadge({ status }: { status: AccessRequestStatus }) {
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

export default function FindPatientPage() {
  const queryClient = useQueryClient();
  const [careVerseId, setCareVerseId] = useState("");
  const [searchedPatient, setSearchedPatient] = useState<PatientDiscoveryResult | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);
  const [isSearching, setIsSearching] = useState(false);

  // Request form state
  const [showRequestForm, setShowRequestForm] = useState(false);
  const [purpose, setPurpose] = useState("");
  const [selectedCategories, setSelectedCategories] = useState<string[]>(["All Records"]);
  const [durationDays, setDurationDays] = useState(30);
  const [requestSuccess, setRequestSuccess] = useState(false);

  // Sent access requests query
  const {
    data: sentData,
    isLoading: isSentLoading,
    error: sentError,
  } = useQuery({
    queryKey: ["access-requests-sent"],
    queryFn: () => accessRequestService.listSent(),
  });

  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    const id = careVerseId.trim();
    if (!id || id.length !== 4 || !/^\d{4}$/.test(id)) {
      setSearchError("Please enter a valid 4-digit numeric CareVerse ID.");
      return;
    }

    setSearchError(null);
    setIsSearching(true);
    setSearchedPatient(null);
    setShowRequestForm(false);
    setRequestSuccess(false);

    try {
      const result = await doctorProfileService.lookupPatientByCareverseId(id);
      setSearchedPatient(result);
    } catch (err) {
      setSearchError(getErrorMessage(err, "Patient not found. Please verify the CareVerse ID."));
    } finally {
      setIsSearching(false);
    }
  };

  const handleCategoryToggle = (category: string) => {
    if (category === "All Records") {
      if (selectedCategories.includes("All Records")) {
        setSelectedCategories([]);
      } else {
        setSelectedCategories(["All Records"]);
      }
      return;
    }

    const withoutAll = selectedCategories.filter((c) => c !== "All Records");
    if (withoutAll.includes(category)) {
      setSelectedCategories(withoutAll.filter((c) => c !== category));
    } else {
      setSelectedCategories([...withoutAll, category]);
    }
  };

  const createRequestMutation = useMutation({
    mutationFn: () => {
      if (!searchedPatient) throw new Error("No patient selected");
      return accessRequestService.create({
        patient_careverse_id: searchedPatient.careverse_id,
        purpose: purpose.trim(),
        requested_categories: selectedCategories.length > 0 ? selectedCategories : ["All Records"],
        requested_duration_days: durationDays,
      });
    },
    onSuccess: () => {
      setRequestSuccess(true);
      setShowRequestForm(false);
      setPurpose("");
      setSelectedCategories(["All Records"]);
      queryClient.invalidateQueries({ queryKey: ["access-requests-sent"] });
    },
  });

  const handleRequestSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!purpose.trim()) return;
    createRequestMutation.mutate();
  };

  const sentRequests = sentData?.items ?? [];

  return (
    <>
      <PageHeader
        title="Find Patient"
        description="Search for patients using their 4-digit CareVerse ID and request access to their medical records."
      />

      <Card title="Search by CareVerse ID" className="mb-6">
        <form onSubmit={handleSearch} className="max-w-md">
          <label htmlFor="careverse-id-input" className="block text-xs font-medium text-slate-700 mb-1">
            4-Digit Patient CareVerse ID
          </label>
          <div className="flex gap-2">
            <input
              id="careverse-id-input"
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              maxLength={4}
              value={careVerseId}
              onChange={(e) => {
                const val = e.target.value.replace(/\D/g, "");
                setCareVerseId(val);
                setSearchError(null);
              }}
              placeholder="e.g. 1024"
              className="w-36 rounded-md border border-slate-300 px-3 py-2 text-center text-lg font-mono font-bold tracking-widest focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
            />
            <Button
              type="submit"
              disabled={careVerseId.length !== 4}
              isLoading={isSearching}
            >
              Lookup Patient
            </Button>
          </div>
          <p className="mt-1.5 text-xs text-slate-500">
            Patients can find their 4-digit ID in their Profile tab.
          </p>
        </form>

        {searchError && (
          <Alert tone="danger" className="mt-4">
            {searchError}
          </Alert>
        )}

        {searchedPatient && (
          <div className="mt-6 rounded-lg border border-teal-200 bg-teal-50/50 p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-teal-800">
                  Patient Identified
                </p>
                <h3 className="text-lg font-bold text-slate-900">{searchedPatient.full_name}</h3>
                <p className="text-xs text-slate-600">
                  CareVerse ID: <span className="font-mono font-semibold">{searchedPatient.careverse_id}</span>
                </p>
              </div>

              {!showRequestForm && (
                <Button
                  onClick={() => setShowRequestForm(true)}
                  variant="primary"
                  size="sm"
                >
                  Request Record Access
                </Button>
              )}
            </div>

            {requestSuccess && (
              <Alert tone="success" className="mt-4">
                Access request submitted successfully! The patient has been notified.
              </Alert>
            )}

            {showRequestForm && (
              <form onSubmit={handleRequestSubmit} className="mt-4 border-t border-teal-200/60 pt-4 space-y-4">
                <Textarea
                  label="Purpose of Access Request"
                  value={purpose}
                  onChange={(e) => setPurpose(e.target.value)}
                  placeholder="e.g. Clinical consultation, reviewing recent lab tests and ongoing medication management."
                  required
                  hint="State clearly why you require access. The patient will review this request."
                />

                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1.5">
                    Requested Categories
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
                    {CATEGORIES.map((cat) => (
                      <label key={cat} className="flex items-center gap-2 text-xs text-slate-700 cursor-pointer">
                        <input
                          type="checkbox"
                          checked={selectedCategories.includes(cat)}
                          onChange={() => handleCategoryToggle(cat)}
                          className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
                        />
                        {cat}
                      </label>
                    ))}
                  </div>
                </div>

                <div className="max-w-xs">
                  <label htmlFor="duration-select" className="block text-sm font-medium text-slate-700 mb-1">
                    Requested Access Duration
                  </label>
                  <select
                    id="duration-select"
                    value={durationDays}
                    onChange={(e) => setDurationDays(Number(e.target.value))}
                    className="w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
                  >
                    {DURATION_OPTIONS.map((opt) => (
                      <option key={opt.days} value={opt.days}>
                        {opt.label}
                      </option>
                    ))}
                  </select>
                </div>

                {createRequestMutation.error && (
                  <Alert tone="danger">
                    {getErrorMessage(createRequestMutation.error, "Could not submit request.")}
                  </Alert>
                )}

                <div className="flex items-center gap-2 pt-2">
                  <Button
                    type="submit"
                    disabled={!purpose.trim()}
                    isLoading={createRequestMutation.isPending}
                  >
                    Submit Access Request
                  </Button>
                  <Button
                    type="button"
                    variant="secondary"
                    onClick={() => setShowRequestForm(false)}
                  >
                    Cancel
                  </Button>
                </div>
              </form>
            )}
          </div>
        )}
      </Card>

      <Card
        title="Sent Access Requests"
        description="Records of patient authorization requests you have submitted."
      >
        {isSentLoading ? (
          <div className="py-8">
            <Spinner label="Loading sent requests" />
          </div>
        ) : sentError ? (
          <Alert tone="danger">
            {getErrorMessage(sentError, "Could not load sent requests.")}
          </Alert>
        ) : sentRequests.length === 0 ? (
          <EmptyState
            title="No sent requests"
            description="You have not sent any record access requests yet."
          />
        ) : (
          <div className="divide-y divide-slate-200">
            {sentRequests.map((req) => (
              <div key={req.id} className="py-3.5 first:pt-0 last:pb-0">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="font-semibold text-slate-900">
                        Patient #{req.patient_careverse_id}
                      </span>
                      <RequestStatusBadge status={req.status} />
                    </div>
                    <p className="mt-1 text-sm text-slate-700">{req.purpose}</p>
                    <div className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-slate-500">
                      <span>Duration: {req.requested_duration_days} days</span>
                      {req.requested_categories && req.requested_categories.length > 0 && (
                        <span>Categories: {req.requested_categories.join(", ")}</span>
                      )}
                      <span>Requested: {formatDateTime(req.created_at)}</span>
                      {req.responded_at && (
                        <span>Responded: {formatDateTime(req.responded_at)}</span>
                      )}
                    </div>
                    {req.status === "rejected" && req.rejection_reason && (
                      <p className="mt-1.5 text-xs text-red-600 bg-red-50 rounded p-1.5 inline-block">
                        Rejection reason: {req.rejection_reason}
                      </p>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>
    </>
  );
}
