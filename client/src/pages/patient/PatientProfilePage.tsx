import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import { Select, Textarea, TextInput } from "../../components/ui/Field";
import DoctorAccessManager from "./DoctorAccessManager";
import { profileService } from "../../services/profile.service";
import { getErrorMessage } from "../../services/api";
import type { PatientProfile, PatientProfileUpdate } from "../../types";

interface FormState {
  full_name: string;
  date_of_birth: string;
  gender: string;
  phone: string;
  address: string;
  notes: string;
}

/** The profile stores nulls; a form field cannot, so they become "". */
function toForm(profile: PatientProfile): FormState {
  return {
    full_name: profile.full_name ?? "",
    date_of_birth: profile.date_of_birth ?? "",
    gender: profile.gender ?? "unspecified",
    phone: profile.phone ?? "",
    address: profile.address ?? "",
    notes: profile.notes ?? "",
  };
}

/**
 * Every field on this screen is something the patient typed. Nothing is
 * computed, inferred or predicted here, and the notes field is explicitly
 * labelled as the patient's own words so it cannot be mistaken for a
 * clinician's observation later.
 */
export default function PatientProfilePage() {
  const queryClient = useQueryClient();

  const { data: profile, isLoading, error: loadError } = useQuery({
    queryKey: ["patient-profile"],
    queryFn: profileService.get,
  });

  const [form, setForm] = useState<FormState | null>(null);
  const [saved, setSaved] = useState(false);

  // Seeded from the first successful load only. Once the patient starts
  // typing we stop overwriting: a background refetch must never discard
  // half-finished input.
  useEffect(() => {
    if (profile && form === null) {
      setForm(toForm(profile));
    }
  }, [profile, form]);

  const save = useMutation({
    mutationFn: (payload: PatientProfileUpdate) => profileService.update(payload),
    onSuccess: (updated) => {
      setSaved(true);
      queryClient.setQueryData(["patient-profile"], updated);
      setForm(toForm(updated));
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Loading your profile" />
      </div>
    );
  }

  if (loadError) {
    return (
      <>
        <PageHeader title="My Profile" description="Your basic details." />
        <Alert tone="danger" title="Your profile could not be loaded">
          {getErrorMessage(loadError, "Please try again in a moment.")}
        </Alert>
      </>
    );
  }

  if (!form || !profile) return null;

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setSaved(false);
    save.reset();
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSaved(false);
    save.mutate({
      // Empty means "no longer set", not "the empty string". Otherwise a
      // cleared phone number would be stored as "" and render as a value.
      full_name: form.full_name.trim(),
      date_of_birth: form.date_of_birth || null,
      gender: (form.gender || "unspecified") as PatientProfileUpdate["gender"],
      phone: form.phone.trim() || null,
      address: form.address.trim() || null,
      notes: form.notes.trim() || null,
    });
  };

  return (
    <>
      <PageHeader
        title="My Profile"
        description="The details you want a doctor to see alongside your records. Only you can read this."
      />

      {saved && (
        <Alert tone="success" title="Profile saved" className="mb-4">
          Your changes are stored on your account.
        </Alert>
      )}
      {save.error && (
        <Alert tone="danger" title="Your changes were not saved" className="mb-4">
          {getErrorMessage(save.error, "Please try again.")}
        </Alert>
      )}

      <form onSubmit={onSubmit} noValidate>
        <Card
          title="Basic details"
          description="Keep these current so your records are identifiable."
          footer="Nothing here is shared with a doctor unless you authorize them below."
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextInput
              label="Full name"
              value={form.full_name}
              onChange={(event) => update("full_name", event.target.value)}
              autoComplete="name"
              required
              maxLength={120}
            />
            <TextInput
              label="Date of birth"
              type="date"
              value={form.date_of_birth}
              onChange={(event) => update("date_of_birth", event.target.value)}
            />
            <Select
              label="Gender"
              value={form.gender}
              onChange={(event) => update("gender", event.target.value)}
            >
              <option value="unspecified">Prefer not to say</option>
              <option value="female">Female</option>
              <option value="male">Male</option>
              <option value="other">Other</option>
            </Select>
            <TextInput
              label="Phone"
              type="tel"
              value={form.phone}
              onChange={(event) => update("phone", event.target.value)}
              autoComplete="tel"
              maxLength={30}
              hint="Optional"
            />
            <TextInput
              label="Address"
              value={form.address}
              onChange={(event) => update("address", event.target.value)}
              autoComplete="street-address"
              maxLength={200}
              hint="Optional"
              className="sm:col-span-2"
            />
            <Textarea
              label="Notes in your own words"
              value={form.notes}
              onChange={(event) => update("notes", event.target.value)}
              maxLength={1000}
              hint="Optional. Anything you want a doctor to know -- allergies, context, or what this record is about. Your words, not a diagnosis."
              className="sm:col-span-2"
            />
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button type="submit" isLoading={save.isPending}>
              Save changes
            </Button>
            <p className="text-sm text-slate-500">All fields except your name are optional.</p>
          </div>
        </Card>
      </form>

      <DoctorAccessManager />
    </>
  );
}
