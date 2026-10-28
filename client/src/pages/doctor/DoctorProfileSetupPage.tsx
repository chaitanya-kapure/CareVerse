import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import Badge from "../../components/ui/Badge";
import { Textarea, TextInput } from "../../components/ui/Field";
import { doctorProfileService } from "../../services/doctor-profile.service";
import { getErrorMessage } from "../../services/api";
import type { DoctorProfile, DoctorProfileUpdate } from "../../types";

interface FormState {
  specialty: string;
  qualifications: string;
  experience_years: string;
  bio: string;
  location: string;
}

function toForm(profile: DoctorProfile): FormState {
  return {
    specialty: profile.specialty ?? "",
    qualifications: profile.qualifications ?? "",
    experience_years:
      profile.experience_years !== null && profile.experience_years !== undefined
        ? String(profile.experience_years)
        : "",
    bio: profile.bio ?? "",
    location: profile.location ?? "",
  };
}

function VerificationBadge({ status }: { status: DoctorProfile["verification_status"] }) {
  switch (status) {
    case "verified":
      return <Badge tone="success">✓ Verified Practitioner</Badge>;
    case "pending":
      return <Badge tone="warning">Verification Under Review</Badge>;
    case "rejected":
      return <Badge tone="danger">Verification Rejected</Badge>;
    default:
      return <Badge tone="neutral">Unverified</Badge>;
  }
}

export default function DoctorProfileSetupPage() {
  const queryClient = useQueryClient();

  const { data: profile, isLoading, error: loadError } = useQuery({
    queryKey: ["my-doctor-profile"],
    queryFn: doctorProfileService.getMyProfile,
  });

  const [form, setForm] = useState<FormState | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (profile && form === null) {
      setForm(toForm(profile));
    }
  }, [profile, form]);

  const saveMutation = useMutation({
    mutationFn: (payload: DoctorProfileUpdate) => doctorProfileService.updateMyProfile(payload),
    onSuccess: (updated) => {
      setSaved(true);
      queryClient.setQueryData(["my-doctor-profile"], updated);
      setForm(toForm(updated));
    },
  });

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Loading clinician profile" />
      </div>
    );
  }

  if (loadError) {
    return (
      <>
        <PageHeader title="Doctor Profile" description="Your professional credentials and public listing." />
        <Alert tone="danger" title="Profile could not be loaded">
          {getErrorMessage(loadError, "Please try again later.")}
        </Alert>
      </>
    );
  }

  if (!form || !profile) return null;

  const update = <K extends keyof FormState>(key: K, value: FormState[K]) => {
    setSaved(false);
    saveMutation.reset();
    setForm((current) => (current ? { ...current, [key]: value } : current));
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setSaved(false);
    const exp = form.experience_years.trim();
    saveMutation.mutate({
      specialty: form.specialty.trim() || undefined,
      qualifications: form.qualifications.trim() || undefined,
      experience_years: exp ? Number(exp) : null,
      bio: form.bio.trim() || undefined,
      location: form.location.trim() || null,
    });
  };

  return (
    <>
      <PageHeader
        title="Clinician Profile"
        description="Manage your professional credentials, medical specialty, and public discovery profile."
      />

      {saved && (
        <Alert tone="success" title="Profile updated successfully" className="mb-4">
          Your professional details have been saved.
        </Alert>
      )}

      {saveMutation.error && (
        <Alert tone="danger" title="Changes could not be saved" className="mb-4">
          {getErrorMessage(saveMutation.error, "Please verify your input and try again.")}
        </Alert>
      )}

      <form onSubmit={onSubmit} noValidate>
        <Card
          title="Professional Credentials & Public Bio"
          description="These details appear to patients searching for clinicians and in social feed posts."
          actions={<VerificationBadge status={profile.verification_status} />}
          footer={
            profile.verification_status !== "verified" ? (
              <p className="text-xs text-amber-800">
                Notice: Your practitioner verification status is currently{" "}
                <strong>{profile.verification_status}</strong>. Verification is reviewed by administrative staff
                against medical licensing registers.
              </p>
            ) : (
              <p className="text-xs text-emerald-800">
                Your medical practitioner profile is fully verified.
              </p>
            )
          }
        >
          <div className="grid gap-4 sm:grid-cols-2">
            <TextInput
              label="Primary Specialty"
              value={form.specialty}
              onChange={(e) => update("specialty", e.target.value)}
              placeholder="e.g. Cardiology, General Medicine, Pediatrics"
              maxLength={100}
              required
            />

            <TextInput
              label="Qualifications & Degrees"
              value={form.qualifications}
              onChange={(e) => update("qualifications", e.target.value)}
              placeholder="e.g. MBBS, MD, MRCP, FACC"
              maxLength={150}
              required
            />

            <TextInput
              label="Years of Experience"
              type="number"
              min={0}
              max={70}
              value={form.experience_years}
              onChange={(e) => update("experience_years", e.target.value)}
              placeholder="e.g. 12"
            />

            <TextInput
              label="Practice Location / Hospital"
              value={form.location}
              onChange={(e) => update("location", e.target.value)}
              placeholder="e.g. City Central Hospital, New York"
              maxLength={150}
            />

            <Textarea
              label="Professional Bio & Clinical Focus"
              value={form.bio}
              onChange={(e) => update("bio", e.target.value)}
              placeholder="Provide a brief clinical biography, areas of medical focus, and research or care philosophy..."
              maxLength={1500}
              className="sm:col-span-2"
            />
          </div>

          <div className="mt-5 flex items-center gap-3">
            <Button type="submit" isLoading={saveMutation.isPending}>
              Save Profile
            </Button>
            <span className="text-xs text-slate-500">
              Community stats: {profile.follower_count} followers • {profile.post_count} posts
            </span>
          </div>
        </Card>
      </form>
    </>
  );
}
