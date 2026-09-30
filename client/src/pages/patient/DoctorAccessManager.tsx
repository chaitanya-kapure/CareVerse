import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import { TextInput } from "../../components/ui/Field";
import { accessService } from "../../services/access.service";
import { getErrorMessage } from "../../services/api";
import { formatDateTime } from "../../utils/format";

const OBJECT_ID = /^[0-9a-fA-F]{24}$/;

/**
 * Who can read this patient's records.
 *
 * This is the whole access mechanism, and it is deliberately small. There is
 * no doctor directory, no search, no invitation and no approval queue: the
 * patient pastes the id of the doctor they already have a relationship with.
 *
 * A directory would be the obvious convenience and the wrong trade. It would
 * turn this screen into a roster of every clinician registered on the
 * platform, and it would let anyone with an account enumerate staff. A
 * patient who is seeing a doctor can get that doctor's id from them; a
 * patient who is *not* cannot learn who works here.
 *
 * Revocation is here for the same reason the grant is: access to medical
 * records has to be withdrawable by the person whose records they are, and a
 * one-way door is not something to ship in a health product.
 */
export default function DoctorAccessManager() {
  const queryClient = useQueryClient();
  const [doctorId, setDoctorId] = useState("");
  const [note, setNote] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [confirmingId, setConfirmingId] = useState<string | null>(null);

  // `isPending`, not `isLoading`: on the first render a React Query
  // observation is pending but not yet fetching. An `isLoading` guard would
  // drop through to the empty state and tell a patient who has just
  // authorized a doctor that nobody has access -- the most alarming possible
  // message to show someone about their own medical records.
  const { data, isPending, error } = useQuery({
    queryKey: ["patient-access"],
    queryFn: accessService.list,
  });

  const grant = useMutation({
    mutationFn: () => accessService.grant({ doctor_id: doctorId.trim(), note: note.trim() || undefined }),
    onSuccess: () => {
      setDoctorId("");
      setNote("");
      setShowForm(false);
      queryClient.invalidateQueries({ queryKey: ["patient-access"] });
    },
  });

  const revoke = useMutation({
    mutationFn: (accessId: string) => accessService.revoke(accessId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["patient-access"] }),
  });

  const grants = data?.items ?? [];
  const active = grants.filter((entry) => entry.status === "active");
  const past = grants.filter((entry) => entry.status === "revoked");
  const trimmed = doctorId.trim();
  const invalid = trimmed.length > 0 && !OBJECT_ID.test(trimmed);

  return (
    <Card
      title="Doctors with access"
      description="Only the doctors you authorize here can read your profile and records."
      className="mt-6"
      actions={
        !showForm ? (
          <Button variant="secondary" size="sm" onClick={() => setShowForm(true)}>
            Authorize a doctor
          </Button>
        ) : null
      }
    >
      {error && (
        <Alert tone="danger" title="Your access list could not be loaded" className="mb-4">
          {getErrorMessage(error, "Please try again in a moment.")}
        </Alert>
      )}

      {showForm && (
        <form
          className="mb-5 rounded-md border border-slate-200 bg-slate-50 p-4"
          noValidate
          onSubmit={(event) => {
            event.preventDefault();
            if (OBJECT_ID.test(trimmed)) grant.mutate();
          }}
        >
          <TextInput
            label="Doctor's CAREVERSE id"
            value={doctorId}
            onChange={(event) => setDoctorId(event.target.value)}
            placeholder="24-character id"
            autoComplete="off"
            spellCheck={false}
            maxLength={24}
            required
            error={invalid ? "That is not a 24-character id." : undefined}
            hint="Ask your doctor for the id shown on their CAREVERSE account. CAREVERSE has no public list of doctors, by design."
          />
          <div className="mt-3">
            <TextInput
              label="Note (optional)"
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={500}
              placeholder="e.g. shared ahead of my appointment on 4 Oct"
              hint="Your own words about why you are sharing. It is stored with the grant and shown only to you."
            />
          </div>
          {grant.error && (
            <Alert tone="danger" title="Access was not granted" className="mt-3">
              {getErrorMessage(grant.error, "Please try again.")}
            </Alert>
          )}
          <div className="mt-4 flex items-center gap-2">
            <Button
              type="submit"
              size="sm"
              isLoading={grant.isPending}
              disabled={!OBJECT_ID.test(trimmed)}
            >
              Grant access
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                setShowForm(false);
                setDoctorId("");
                setNote("");
                grant.reset();
              }}
            >
              Cancel
            </Button>
          </div>
        </form>
      )}

      {isPending ? (
        <div className="py-6">
          <Spinner label="Loading your access list" />
        </div>
      ) : grants.length === 0 ? (
        <EmptyState
          title="No doctor has access to your records"
          description="Your records are readable only by you. Authorize a specific doctor above when you want them to have access."
        />
      ) : (
        <ul className="divide-y divide-slate-200">
          {[...active, ...past].map((entry) => (
            <li key={entry.id} className="flex flex-wrap items-start justify-between gap-3 py-3">
              <div className="min-w-0">
                <p className="text-sm font-medium text-slate-900">
                  {entry.doctor_name || "Unnamed doctor"}
                </p>
                <p className="mt-0.5 text-xs text-slate-500">
                  {entry.status === "active" ? "Granted" : "Revoked"}{" "}
                  {formatDateTime(entry.granted_at)}
                  <span aria-hidden="true"> &middot; </span>
                  <span className="font-mono">{entry.doctor_id}</span>
                </p>
                {entry.note && (
                  <p className="mt-1 text-xs italic text-slate-600">&ldquo;{entry.note}&rdquo;</p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {entry.status === "active" ? (
                  <>
                    <Badge tone="success">Active</Badge>
                    <Button
                      variant="secondary"
                      size="sm"
                      isLoading={revoke.isPending && confirmingId === entry.id}
                      onBlur={() => setConfirmingId(null)}
                      onClick={() => {
                        // Two clicks, not a modal: the control stays
                        // keyboard-reachable and a stray click cannot end
                        // someone's access.
                        if (confirmingId === entry.id) revoke.mutate(entry.id);
                        else setConfirmingId(entry.id);
                      }}
                    >
                      {confirmingId === entry.id ? "Click again to confirm" : "Revoke"}
                    </Button>
                  </>
                ) : (
                  <Badge tone="neutral">Revoked</Badge>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}

      {revoke.error && (
        <Alert tone="danger" title="Access was not revoked" className="mt-3">
          {getErrorMessage(revoke.error, "Please try again.")}
        </Alert>
      )}
    </Card>
  );
}
