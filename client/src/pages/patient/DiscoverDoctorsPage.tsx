import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import Spinner from "../../components/ui/Spinner";
import EmptyState from "../../components/ui/EmptyState";
import Badge from "../../components/ui/Badge";
import { doctorProfileService } from "../../services/doctor-profile.service";
import { getErrorMessage } from "../../services/api";
import type { DoctorProfile } from "../../types";

const SPECIALTIES = [
  "General Medicine",
  "Cardiology",
  "Neurology",
  "Orthopedics",
  "Dermatology",
  "Pediatrics",
  "Psychiatry",
  "Oncology",
  "Endocrinology",
  "Other",
];

function VerificationBadge({ status }: { status: DoctorProfile["verification_status"] }) {
  switch (status) {
    case "verified":
      return <Badge tone="success">✓ Verified</Badge>;
    case "pending":
      return <Badge tone="warning">Pending Review</Badge>;
    case "rejected":
      return <Badge tone="danger">Rejected</Badge>;
    default:
      return <Badge tone="neutral">Unverified</Badge>;
  }
}

function DoctorCard({ doctor }: { doctor: DoctorProfile }) {
  const queryClient = useQueryClient();

  const followMutation = useMutation({
    mutationFn: () => doctorProfileService.follow(doctor.user_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["doctors"] }),
  });

  const unfollowMutation = useMutation({
    mutationFn: () => doctorProfileService.unfollow(doctor.user_id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["doctors"] }),
  });

  const isPending = followMutation.isPending || unfollowMutation.isPending;

  return (
    <Card className="flex flex-col justify-between h-full">
      <div>
        <div className="flex items-start justify-between gap-2">
          <div>
            <h3 className="text-base font-semibold text-slate-900">{doctor.name}</h3>
            <p className="text-sm font-medium text-teal-700">{doctor.specialty || "General Physician"}</p>
          </div>
          <VerificationBadge status={doctor.verification_status} />
        </div>

        {doctor.qualifications && (
          <p className="mt-2 text-xs text-slate-600 font-mono bg-slate-50 rounded px-2 py-1 inline-block">
            {doctor.qualifications}
          </p>
        )}

        {doctor.experience_years !== null && doctor.experience_years !== undefined && (
          <p className="mt-1 text-xs text-slate-500">
            {doctor.experience_years} {doctor.experience_years === 1 ? "year" : "years"} experience
            {doctor.location ? ` • ${doctor.location}` : ""}
          </p>
        )}

        {doctor.bio && (
          <p className="mt-3 text-sm text-slate-600 line-clamp-3">
            {doctor.bio}
          </p>
        )}
      </div>

      <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-3">
        <div className="text-xs text-slate-500">
          <span className="font-semibold text-slate-700">{doctor.follower_count}</span> followers
          {doctor.post_count > 0 && (
            <>
              <span aria-hidden="true"> • </span>
              <span className="font-semibold text-slate-700">{doctor.post_count}</span> posts
            </>
          )}
        </div>

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
            Follow
          </Button>
        )}
      </div>
    </Card>
  );
}

export default function DiscoverDoctorsPage() {
  const [name, setName] = useState("");
  const [specialty, setSpecialty] = useState("");
  const [verifiedOnly, setVerifiedOnly] = useState(false);

  const filters = {
    name: name.trim() || undefined,
    specialty: specialty || undefined,
    verified_only: verifiedOnly || undefined,
  };

  const { data, isLoading, error } = useQuery({
    queryKey: ["doctors", filters],
    queryFn: () => doctorProfileService.discoverDoctors(filters),
  });

  const doctors = data?.items ?? [];

  return (
    <>
      <PageHeader
        title="Discover Doctors"
        description="Find qualified medical specialists, follow verified clinicians, and stay updated with health insights."
      />

      <Card className="mb-6">
        <div className="grid gap-4 sm:grid-cols-3">
          <div>
            <label htmlFor="search-name" className="block text-xs font-medium text-slate-700 mb-1">
              Search by name
            </label>
            <input
              id="search-name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="e.g. Dr. Smith"
              className="w-full rounded-md border border-slate-300 px-3 py-1.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
            />
          </div>

          <div>
            <label htmlFor="filter-specialty" className="block text-xs font-medium text-slate-700 mb-1">
              Specialty
            </label>
            <select
              id="filter-specialty"
              value={specialty}
              onChange={(e) => setSpecialty(e.target.value)}
              className="w-full rounded-md border border-slate-300 bg-white px-3 py-1.5 text-sm focus:border-teal-600 focus:outline-none focus:ring-1 focus:ring-teal-600"
            >
              <option value="">All Specialties</option>
              {SPECIALTIES.map((spec) => (
                <option key={spec} value={spec}>
                  {spec}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center sm:pt-5">
            <label className="flex items-center gap-2 cursor-pointer text-sm text-slate-700">
              <input
                type="checkbox"
                checked={verifiedOnly}
                onChange={(e) => setVerifiedOnly(e.target.checked)}
                className="h-4 w-4 rounded border-slate-300 text-teal-600 focus:ring-teal-500"
              />
              Verified doctors only
            </label>
          </div>
        </div>
      </Card>

      {isLoading ? (
        <div className="py-12">
          <Spinner label="Searching doctors" />
        </div>
      ) : error ? (
        <Alert tone="danger" title="Could not load doctors">
          {getErrorMessage(error, "Please try again later.")}
        </Alert>
      ) : doctors.length === 0 ? (
        <EmptyState
          title="No doctors found"
          description="Try broadening your search criteria or clearing filters."
        />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {doctors.map((doctor) => (
            <DoctorCard key={doctor.id} doctor={doctor} />
          ))}
        </div>
      )}
    </>
  );
}
