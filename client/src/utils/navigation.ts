/**
 * Role-based navigation.
 *
 * Kept as data so the sidebar, breadcrumbs and any future command palette
 * all read from one list, and so adding a screen in a later phase is a
 * one-line change here.
 */

import type { UserRole } from "../types";

export interface NavItem {
  label: string;
  to: string;
  /** Marks the link active on the index route as well as nested routes. */
  end?: boolean;
}

export const PATIENT_NAV: NavItem[] = [
  { label: "Dashboard", to: "/patient", end: true },
  { label: "My Profile", to: "/patient/profile" },
  { label: "Medical Records", to: "/patient/records" },
  { label: "Upload Record", to: "/patient/records/upload" },
];

export const DOCTOR_NAV: NavItem[] = [
  { label: "Dashboard", to: "/doctor", end: true },
  { label: "Authorized Patients", to: "/doctor/patients" },
  { label: "Patient Records", to: "/doctor/patients/records" },
  { label: "Patient Summary", to: "/doctor/patients/summary" },
];

export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  patient: PATIENT_NAV,
  doctor: DOCTOR_NAV,
};

export function dashboardPathFor(role: UserRole): string {
  return role === "doctor" ? "/doctor" : "/patient";
}
