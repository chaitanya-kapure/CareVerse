import { useContext } from "react";
import { AuthContext, type AuthContextValue } from "../context/authContext";

/** Access the authenticated user, token and session status. */
export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth must be used within an AuthProvider");
  }
  return context;
}
