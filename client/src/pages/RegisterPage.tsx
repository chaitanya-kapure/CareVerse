import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authService } from "../services/auth.service";
import { getErrorMessage } from "../services/api";
import Button from "../components/ui/Button";
import Alert from "../components/ui/Alert";
import { Select, TextInput } from "../components/ui/Field";
import type { UserRole } from "../types";

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState<UserRole>("patient");
  const navigate = useNavigate();

  const { mutate: submit, isPending, error } = useMutation({
    mutationFn: () => authService.register({ name, email, password, role }),
    onSuccess: () => {
      // Registration does not sign the user in; they land on login so the
      // first authenticated action is always an explicit credential check.
      navigate("/login", { replace: true, state: { registered: true } });
    },
  });

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault();
    submit();
  };

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900">Create an account</h1>
      <p className="mt-1 text-sm text-slate-500">
        Patients manage their records. Doctors review patients who authorize them.
      </p>

      {error && (
        <Alert tone="danger" className="mt-4">
          {getErrorMessage(error, "Registration failed")}
        </Alert>
      )}

      <form onSubmit={handleSubmit} className="mt-6 space-y-4" noValidate>
        <Select
          label="I am registering as"
          value={role}
          onChange={(event) => setRole(event.target.value as UserRole)}
          hint={
            role === "patient"
              ? "You will be able to upload and manage your own medical records."
              : "You will be able to review patients who have authorized you."
          }
        >
          <option value="patient">Patient</option>
          <option value="doctor">Doctor</option>
        </Select>

        <TextInput
          label="Full name"
          name="name"
          autoComplete="name"
          required
          value={name}
          onChange={(event) => setName(event.target.value)}
        />
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
          autoComplete="new-password"
          required
          minLength={6}
          hint="At least 6 characters."
          value={password}
          onChange={(event) => setPassword(event.target.value)}
        />

        <Button type="submit" isLoading={isPending} className="w-full">
          Create account
        </Button>
      </form>

      <p className="mt-5 text-sm text-slate-600">
        Already registered?{" "}
        <Link to="/login" className="font-medium text-teal-700 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
