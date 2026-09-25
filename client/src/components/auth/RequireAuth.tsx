import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "../../hooks/useAuth";
import Spinner from "../ui/Spinner";
import type { ReactNode } from "react";
import type { UserRole } from "../../types";

interface RequireAuthProps {
  allowedRole: UserRole;
  children: ReactNode;
}

/**
 * Client-side route guard.
 *
 * This is UX only. It stops a signed-out user from seeing a protected
 * screen, but it is not a security control -- every protected page also
 * calls a protected API endpoint, and the server re-checks authorization on
 * each request.
 */
export default function RequireAuth({ allowedRole, children }: RequireAuthProps) {
  const { user, status } = useAuth();
  const location = useLocation();

  if (status === "loading") {
    return (
      <div className="flex min-h-[60vh] items-center justify-center">
        <Spinner label="Checking your session" />
      </div>
    );
  }

  if (status === "unauthenticated") {
    // Remember where they were headed so login can return them there.
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }

  if (user?.role !== allowedRole) {
    // Send them to their own dashboard instead of a dead-end login page.
    return <Navigate to={user?.role === "doctor" ? "/doctor" : "/patient"} replace />;
  }

  return <>{children}</>;
}
