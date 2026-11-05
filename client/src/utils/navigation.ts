/**
 * Role-based navigation with icons and categories.
 */

import type { UserRole } from "../types";

export interface NavItem {
  label: string;
  to: string;
  end?: boolean;
  icon?: string;
  section?: "core" | "connect" | "account";
}

export const PATIENT_NAV: NavItem[] = [
  { label: "Dashboard", to: "/patient", end: true, icon: "📊", section: "core" },
  { label: "Medical Records", to: "/patient/records", icon: "📁", section: "core" },
  { label: "Upload Record", to: "/patient/records/upload", icon: "📤", section: "core" },
  { label: "AI Health Summary", to: "/patient/summary", icon: "🧠", section: "core" },

  { label: "Discover Doctors", to: "/patient/discover", icon: "👨‍⚕️", section: "connect" },
  { label: "Access Requests", to: "/patient/access-requests", icon: "🔐", section: "connect" },
  { label: "Social Feed", to: "/patient/feed", icon: "🌐", section: "connect" },
  { label: "Messages", to: "/patient/messages", icon: "💬", section: "connect" },
  { label: "Notifications", to: "/patient/notifications", icon: "🔔", section: "connect" },

  { label: "My Profile", to: "/patient/profile", icon: "👤", section: "account" },
];

export const DOCTOR_NAV: NavItem[] = [
  { label: "Dashboard", to: "/doctor", end: true, icon: "📊", section: "core" },
  { label: "Authorized Patients", to: "/doctor/patients", icon: "👥", section: "core" },
  { label: "Find Patient", to: "/doctor/find-patient", icon: "🔍", section: "core" },

  { label: "Social Feed", to: "/doctor/feed", icon: "🌐", section: "connect" },
  { label: "Messages", to: "/doctor/messages", icon: "💬", section: "connect" },
  { label: "Notifications", to: "/doctor/notifications", icon: "🔔", section: "connect" },

  { label: "Doctor Profile", to: "/doctor/profile", icon: "👨‍⚕️", section: "account" },
];

export const NAV_BY_ROLE: Record<UserRole, NavItem[]> = {
  patient: PATIENT_NAV,
  doctor: DOCTOR_NAV,
};

export function dashboardPathFor(role: UserRole): string {
  return role === "doctor" ? "/doctor" : "/patient";
}
