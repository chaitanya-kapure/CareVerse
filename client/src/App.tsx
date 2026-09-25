import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";

import { AuthProvider } from "./context/AuthProvider";
import RequireAuth from "./components/auth/RequireAuth";
import AppShell from "./layouts/AppShell";
import AuthLayout from "./layouts/AuthLayout";

import LandingPage from "./pages/LandingPage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import NotFoundPage from "./pages/NotFoundPage";

import PatientDashboardPage from "./pages/patient/PatientDashboardPage";
import PatientProfilePage from "./pages/patient/PatientProfilePage";
import MedicalRecordsPage from "./pages/patient/MedicalRecordsPage";
import UploadRecordPage from "./pages/patient/UploadRecordPage";
import RecordDetailsPage from "./pages/patient/RecordDetailsPage";

import DoctorDashboardPage from "./pages/doctor/DoctorDashboardPage";
import AuthorizedPatientsPage from "./pages/doctor/AuthorizedPatientsPage";
import PatientDetailsPage from "./pages/doctor/PatientDetailsPage";
import PatientRecordsPage from "./pages/doctor/PatientRecordsPage";
import PatientSummaryPage from "./pages/doctor/PatientSummaryPage";

/**
 * Route table.
 *
 * Every protected screen sits behind RequireAuth for UX, and every one of
 * them will also call a protected API endpoint — RequireAuth is never the
 * thing that enforces access.
 */
export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          {/* Public */}
          <Route path="/" element={<LandingPage />} />
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<LoginPage />} />
            <Route path="/register" element={<RegisterPage />} />
          </Route>

          {/* Patient */}
          <Route
            path="/patient"
            element={
              <RequireAuth allowedRole="patient">
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<PatientDashboardPage />} />
            <Route path="profile" element={<PatientProfilePage />} />
            <Route path="records" element={<MedicalRecordsPage />} />
            <Route path="records/upload" element={<UploadRecordPage />} />
            <Route path="records/:documentId" element={<RecordDetailsPage />} />
          </Route>

          {/* Doctor */}
          <Route
            path="/doctor"
            element={
              <RequireAuth allowedRole="doctor">
                <AppShell />
              </RequireAuth>
            }
          >
            <Route index element={<DoctorDashboardPage />} />
            <Route path="patients" element={<AuthorizedPatientsPage />} />
            <Route path="patients/:patientId" element={<PatientDetailsPage />} />
            <Route path="patients/:patientId/records" element={<PatientRecordsPage />} />
            <Route path="patients/:patientId/summary" element={<PatientSummaryPage />} />
          </Route>

          {/* Root is role-dependent; send signed-in users to their own area. */}
          <Route path="/dashboard" element={<Navigate to="/patient" replace />} />
          <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
  );
}
