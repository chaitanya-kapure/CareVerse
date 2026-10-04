import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import DetailRow from "../../components/DetailRow";
import SummarySectionCard from "../../components/SummarySectionCard";
import { summaryService } from "../../services/summary.service";
import { documentService } from "../../services/document.service";
import { getErrorMessage } from "../../services/api";
import { formatDateTime } from "../../utils/format";
import { isWorthRetrying } from "../../utils/query";
import {
  MOCK_SUMMARY_LABEL,
  NOT_A_DIAGNOSIS_NOTICE,
} from "../../utils/disclaimers";

/**
 * The signed-in patient's own summary.
 *
 * The same document a doctor reads, from the other side, and rendered in the
 * same order for the same reason: the disclaimer and the mock label come
 * before anything the summary says, so a claim is never reached without having
 * first been told what produced it and that it is not a clinical judgment.
 * A patient is the audience most likely to read this as a clinical result,
 * because they are the one who uploaded the paperwork and knows what was
 * worrying them. Wording it identically to the doctor screen is what stops the
 * two from implying different levels of authority.
 *
 * Three things are deliberately absent.
 *
 * There is no rebuild button. `/patients/me/summary` generates on demand and
 * has no POST sibling, so the only way to refresh this screen is to reload it
 * — and that is honest, because a patient has nothing to add to a summary
 * whose every line is copied from a record they already uploaded.
 *
 * There is no patient id anywhere. Not in the path, not in the query, so there
 * is nothing on this screen for a patient to change in order to read somebody
 * else's summary. The server resolves the id from the token.
 *
 * And the record list is fetched separately, exactly as on the doctor screen.
 * The summary carries ids rather than titles, and the record list is what the
 * patient actually uploaded. Where the two disagree — always, for a scanned
 * document — the record list is the truth.
 */
export default function PatientSummaryPage() {
  const summary = useQuery({
    queryKey: ["own-summary"],
    queryFn: summaryService.getOwn,
    retry: isWorthRetrying,
  });

  const records = useQuery({
    queryKey: ["medical-documents"],
    queryFn: documentService.list,
    retry: isWorthRetrying,
  });

  // `isPending`, not `isLoading`: a first render is pending-but-idle, and an
  // `isLoading` guard falls through to the success path and renders a summary
  // full of "not found in the uploaded records" for a patient who has simply
  // not loaded yet.
  if (summary.isError || records.isError) {
    return (
      <>
        <PageHeader title="My summary" />
        <EmptyState
          title="Your summary could not be loaded"
          description={getErrorMessage(
            summary.error ?? records.error,
            "Please try again in a moment.",
          )}
          action={
            <Link to="/patient/records">
              <Button variant="secondary">Back to my records</Button>
            </Link>
          }
        />
      </>
    );
  }

  if (summary.isPending || records.isPending) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Building your summary" />
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
        title="My summary"
        description="Assembled from the records you have uploaded. Every line below links to the record it came from."
        actions={
          <Link to="/patient/records">
            <Button variant="secondary" size="sm">
              View all my records
            </Button>
          </Link>
        }
      />

      {data && (
        <div className="space-y-4">
          {/* 1. The disclaimer, before anything the summary says. */}
          <Alert tone="info" title="About this summary" className="mb-4">
            <p>{data.disclaimer}</p>
            <p className="mt-2">{NOT_A_DIAGNOSIS_NOTICE}</p>
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
              documentHref={(documentId) => `/patient/records/${documentId}`}
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
                      to={`/patient/records/${record.id}`}
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
            description="Provenance, so you can judge how much of your record set this covers."
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
              <p className="mt-4 text-sm text-slate-600">
                A record CAREVERSE could not read is left out rather than
                guessed at. If one of these is a scan, the original PDF is
                still in your records and nothing was lost.
              </p>
            )}
          </Card>
        </div>
      )}
    </>
  );
}