import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Badge from "../../components/ui/Badge";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import DetailRow from "../../components/DetailRow";
import SummarySectionCard from "../../components/SummarySectionCard";
import { summaryService } from "../../services/summary.service";
import { doctorService } from "../../services/doctor.service";
import { getErrorCode, getErrorMessage } from "../../services/api";
import { formatDateTime } from "../../utils/format";
import { isWorthRetrying } from "../../utils/query";
import {
  MOCK_SUMMARY_LABEL,
  NOT_A_DIAGNOSIS_READER_NOTICE,
} from "../../utils/disclaimers";

/**
 * One authorized patient's summary.
 *
 * Rendered in a fixed order, and the order is the safety model: the disclaimer
 * and the mock label come before anything the summary says, so a reader cannot
 * reach a claim without having first been told what produced it and that it is
 * not a clinical judgment.
 *
 * Two separate sources of truth are on this screen and they must not be
 * confused. The summary says what CAREVERSE extracted; the record list beside
 * it is what the patient actually uploaded. When they disagree — and on a
 * scanned document they always do, because that document is counted as
 * unreadable — the record list is the truth and the summary says so itself.
 *
 * The `patientId` in the URL is attacker-controlled as far as the browser is
 * concerned and is passed straight through. That is safe only because the
 * server authorizes it on every request; an ungranted and a nonexistent
 * patient produce the same `403`, and this screen must not imply which.
 */
export default function PatientSummaryPage() {
  const { patientId = "" } = useParams();
  const queryClient = useQueryClient();

  const summaryKey = ["doctor-patient-summary", patientId];

  const summary = useQuery({
    queryKey: summaryKey,
    queryFn: () => summaryService.getForPatient(patientId),
    enabled: Boolean(patientId),
    retry: isWorthRetrying,
  });

  // Only for the source-document list: the summary carries ids, not titles,
  // and a list of bare ids is not something a clinician can navigate from.
  const records = useQuery({
    queryKey: ["doctor-patient-documents", patientId],
    queryFn: () => doctorService.listDocuments(patientId),
    enabled: Boolean(patientId),
    retry: isWorthRetrying,
  });

  const regenerate = useMutation({
    mutationFn: () => summaryService.regenerate(patientId),
    onSuccess: (fresh) => {
      // Written straight into the cache rather than left to an invalidation
      // round trip, so the screen shows the summary it just asked for instead
      // of briefly rendering the old one it asked to replace.
      queryClient.setQueryData(summaryKey, fresh);
    },
  });

  const backToPatient = `/doctor/patients/${patientId}`;

  // `isPending`, not `isLoading`: a first render is pending-but-idle, and an
  // `isLoading` guard falls through to the success path and renders a summary
  // full of "not found in the uploaded records" for a patient who has simply
  // not loaded yet. Same reasoning as the other doctor screens.
  if (summary.isError || records.isError) {
    const forbidden =
      getErrorCode(summary.error) === "NO_PATIENT_ACCESS" ||
      getErrorCode(records.error) === "NO_PATIENT_ACCESS";

    return (
      <>
        <PageHeader title="Patient summary" />
        <EmptyState
          title={
            forbidden
              ? "You do not have access to this patient's summary"
              : "This summary could not be loaded"
          }
          description={
            forbidden
              ? "A patient has to authorize you before their records become available. This is the same response whether or not an account exists with that id."
              : getErrorMessage(
                  summary.error ?? records.error,
                  "Please try again in a moment.",
                )
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

  if (summary.isPending || records.isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Building this patient's summary" />
      </div>
    );
  }

  const data = summary.data;
  const allRecords = records.data?.items ?? [];
  const sourceIds = data?.source_document_ids ?? [];
  const sourceRecords = allRecords.filter((record) => sourceIds.includes(record.id));

  return (
    <>
      <PageHeader
        title="Patient summary"
        description="Assembled from the records this patient has uploaded. Read-only, like every other doctor screen."
        actions={
          <Button
            variant="secondary"
            size="sm"
            onClick={() => regenerate.mutate()}
            isLoading={regenerate.isPending}
          >
            Rebuild from current records
          </Button>
        }
      />

      <div className="mb-4 flex flex-wrap items-center gap-2">
        <Link to={backToPatient}>
          <Button variant="secondary" size="sm">
            Back to this patient
          </Button>
        </Link>
      </div>

      {regenerate.isError && (
        <Alert tone="danger" title="The summary could not be rebuilt" className="mb-4">
          {getErrorMessage(regenerate.error, "Please try again in a moment.")}
        </Alert>
      )}

      {data && (
        <div className="space-y-4">
          {/* 1. The disclaimer, before anything the summary says. */}
          <Alert tone="info" title="About this summary" className="mb-4">
            <p>{data.disclaimer}</p>
            <p className="mt-2">{NOT_A_DIAGNOSIS_READER_NOTICE}</p>
          </Alert>

          {/* 2. What produced it, before any of its content. */}
          {data.is_mock && (
            <Alert tone="warning" title="Deterministic demo summary" className="mb-4">
              {MOCK_SUMMARY_LABEL}
            </Alert>
          )}

          {/* 3. The framing sentence. */}
          <Card title="Overview">
            <p className="text-sm text-slate-700">{data.overview}</p>
          </Card>

          {/* 4. The sections, in the order the server defines. */}
          {data.sections.map((section) => (
            <SummarySectionCard
              key={section.key}
              section={section}
              documentHref={(documentId) =>
                `/doctor/patients/${patientId}/records/${documentId}`
              }
            />
          ))}

          {/* 5. The records this came from, each one click away. */}
          <Card
            title="Source records"
            description="Every record below contributed a line above."
          >
            {sourceRecords.length === 0 ? (
              <p className="text-sm italic text-slate-500">
                No records have been read yet, so there is nothing to link to.
              </p>
            ) : (
              <ul className="divide-y divide-slate-200">
                {sourceRecords.map((record) => (
                  <li key={record.id}>
                    <Link
                      to={`/doctor/patients/${patientId}/records/${record.id}`}
                      className="-mx-2 flex flex-wrap items-center justify-between gap-3 rounded-md px-2 py-3 transition-colors hover:bg-slate-50"
                    >
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium text-slate-900">
                          {record.title}
                        </p>
                        <p className="mt-0.5 truncate text-xs text-slate-500">
                          {record.original_filename}
                        </p>
                      </div>
                    </Link>
                  </li>
                ))}
              </ul>
            )}
          </Card>

          {/* 6. What went into it, including what did not. */}
          <Card
            title="How this was built"
            description="Provenance, so a reader can judge how much of the record set this covers."
          >
            <dl className="divide-y divide-slate-100 text-sm">
              <DetailRow
                label="Generated"
                value={formatDateTime(data.generated_at)}
                empty="Not recorded"
              />
              <DetailRow
                label="Records in this summary"
                value={`${data.source_document_count} of ${allRecords.length} uploaded`}
              />
              <DetailRow
                label="Records that could not be read"
                value={
                  data.unreadable_document_count === 0
                    ? "None"
                    : `${data.unreadable_document_count} (scanned or unreadable — excluded, not guessed at)`
                }
              />
              <DetailRow label="Produced by" value={data.provider} />
              <DetailRow
                label="Language model"
                value={data.model}
                empty="None — this summary is assembled by pattern matching"
              />
              <DetailRow
                label="Demo output"
                value={data.is_mock ? "Yes" : "No"}
              />
            </dl>
            {data.unreadable_document_count > 0 && (
              <div className="mt-4">
                <Badge tone="warning">
                  {data.unreadable_document_count} unreadable record
                  {data.unreadable_document_count === 1 ? "" : "s"} excluded
                </Badge>
              </div>
            )}
          </Card>
        </div>
      )}
    </>
  );
}
