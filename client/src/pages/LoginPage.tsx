import { useState, type FormEvent } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { authService } from "../services/auth.service";
import { getErrorMessage } from "../services/api";
import { dashboardPathFor } from "../utils/navigation";
import Button from "../components/ui/Button";
import Alert from "../components/ui/Alert";
import { TextInput } from "../components/ui/Field";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const { login } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const redirectTo = (location.state as { from?: string } | null)?.from;

  const { mutate: submit, isPending, error } = useMutation({
    mutationFn: () => authService.login({ email, password }),
    onSuccess: (auth) => {
      login(auth);
      // Honour the page they were originally trying to reach, but never
      // bounce them into the other role's area.
      const fallback = dashboardPathFor(auth.user.role);
      navigate(redirectTo ?? fallback, { replace: true });
    },
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900">Sign in</h1>
      <p className="mt-1 text-sm text-slate-500">
        Access your CAREVERSE patient or doctor account.
      </p>

      {error && (
        <Alert tone="danger" className="mt-4">
          {getErrorMessage(error, "Sign in failed")}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        <TextInput
          label="Email"
          type="email"
          name="email"
          autoComplete="email"
          required
          value={email}
          onChange={(event) => setEmail(event.target.value)}
        />
        <TextInput
          label="Password"
          type="password"
          name="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />
        <Button type="submit" isLoading={isPending} className="w-full">
          Sign in
        </Button>

        <p className="text-center text-sm">
          <Link
            to="/forgot-password"
            className="text-slate-600 underline underline-offset-2 hover:text-slate-900"
          >
            Forgot your password?
          </Link>
        </p>
      </form>

      <p className="mt-5 text-sm text-slate-600">
        Need an account?{" "}
        <Link to="/register" className="font-medium text-teal-700 hover:underline">
          Register
        </Link>
      </p>
    </div>
  );
}
