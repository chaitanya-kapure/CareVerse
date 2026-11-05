import { Link, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import DetailRow from "../../components/DetailRow";
import { doctorProfileService } from "../../services/doctor-profile.service";
import { getErrorMessage } from "../../services/api";

export default function DoctorPublicProfilePage() {
  const { userId = "" } = useParams();
  const queryClient = useQueryClient();

  const {
    data: doctor,
    isLoading,
    error,
  } = useQuery({
    queryKey: ["doctor-public-profile", userId],
    queryFn: () => doctorProfileService.getProfile(userId),
    enabled: Boolean(userId),
  });

  const followMutation = useMutation({
    mutationFn: () => doctorProfileService.follow(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-public-profile", userId] });
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
    },
  });

  const unfollowMutation = useMutation({
    mutationFn: () => doctorProfileService.unfollow(userId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["doctor-public-profile", userId] });
      queryClient.invalidateQueries({ queryKey: ["doctors"] });
    },
  });

  const isPending = followMutation.isPending || unfollowMutation.isPending;

  if (isLoading) {
    return (
      <div className="flex min-h-[40vh] items-center justify-center">
        <Spinner label="Loading clinician profile..." />
      </div>
    );
  }

  if (error || !doctor) {
    return (
      <>
        <PageHeader title="Doctor Profile" />
        <EmptyState
          title="Doctor profile not found"
          description={getErrorMessage(
            error,
            "The requested clinician profile could not be loaded or may no longer be available."
          )}
          action={
            <Link to="/patient/discover">
              <Button variant="secondary">Back to Discover Doctors</Button>
            </Link>
          }
        />
      </>
    );
  }

  const isVerified = doctor.verification_status === "verified";

  return (
    <>
      <div className="mb-4">
        <Link
          to="/patient/discover"
          className="inline-flex items-center gap-1.5 text-sm font-semibold text-teal-700 hover:text-teal-900 transition-colors"
        >
          ← Back to Discover Doctors
        </Link>
      </div>

      <PageHeader
        title={doctor.name ? `Dr. ${doctor.name.replace(/^Dr\.?\s+/i, "")}` : "Doctor Profile"}
        description={`${doctor.specialty || "Medical Specialist"} • Clinical Profile & Background`}
        actions={
          <div className="flex items-center gap-2">
            {isVerified && <Badge tone="success">✓ Verified Clinician</Badge>}
            {doctor.is_following ? (
              <Button
                variant="secondary"
                size="sm"
                isLoading={isPending}
                onClick={() => unfollowMutation.mutate()}
              >
                Following
              </Button>
            ) : (
              <Button
                variant="primary"
                size="sm"
                isLoading={isPending}
                onClick={() => followMutation.mutate()}
              >
                + Follow Clinician
              </Button>
            )}
          </div>
        }
      />

      <div className="grid gap-6 lg:grid-cols-3">
        {/* Left Column: Quick Stats & Clinical Contact */}
        <div className="space-y-6 lg:col-span-1">
          <Card title="Clinician Information">
            <dl className="divide-y divide-slate-100 text-sm">
              <DetailRow label="Full Name" value={doctor.name} />
              <DetailRow label="Primary Specialty" value={doctor.specialty || "General Medicine"} />
              <DetailRow
                label="Qualifications"
                value={doctor.qualifications || null}
                empty="Degrees / Certifications on file"
              />
              <DetailRow
                label="Clinical Experience"
                value={
                  doctor.experience_years !== null && doctor.experience_years !== undefined
                    ? `${doctor.experience_years} ${doctor.experience_years === 1 ? "year" : "years"}`
                    : null
                }
                empty="Not specified"
              />
              <DetailRow
                label="Practice Location"
                value={doctor.location || null}
                empty="Hospital / Clinic not specified"
              />
            </dl>
          </Card>

          <Card title="Network & Community">
            <div className="flex items-center justify-around py-2 text-center">
              <div>
                <p className="text-2xl font-bold text-slate-900">{doctor.follower_count}</p>
                <p className="text-xs text-slate-500 font-medium">Followers</p>
              </div>
              <div className="h-8 w-px bg-slate-200" />
              <div>
                <p className="text-2xl font-bold text-slate-900">{doctor.post_count}</p>
                <p className="text-xs text-slate-500 font-medium">Health Posts</p>
              </div>
            </div>
          </Card>

          <Card title="Patient Care Sharing">
            <div className="space-y-3 text-xs text-slate-600">
              <p>
                Want this doctor to review your medical history? You can grant them access to your records
                anytime from your Access Requests page.
              </p>
              <Link to="/patient/access-requests" className="block">
                <Button variant="secondary" size="sm" className="w-full justify-center">
                  Manage Doctor Access
                </Button>
              </Link>
            </div>
          </Card>
        </div>

        {/* Right Column: Clinical Bio & Professional Background */}
        <div className="space-y-6 lg:col-span-2">
          <Card title="Professional Background & Biography">
            {doctor.bio ? (
              <p className="whitespace-pre-wrap text-sm leading-relaxed text-slate-700">
                {doctor.bio}
              </p>
            ) : (
              <p className="text-sm text-slate-500 italic">
                This doctor has not provided a public biography yet.
              </p>
            )}

            {doctor.qualifications && (
              <div className="mt-6 border-t border-slate-100 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-500 mb-2">
                  Degrees &amp; Certifications
                </h4>
                <div className="flex flex-wrap gap-2">
                  {doctor.qualifications.split(/[,;]+/).map((deg, i) => (
                    <span
                      key={i}
                      className="rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-xs font-mono font-medium text-slate-700"
                    >
                      {deg.trim()}
                    </span>
                  ))}
                </div>
              </div>
            )}
          </Card>
        </div>
      </div>
    </>
  );
}
