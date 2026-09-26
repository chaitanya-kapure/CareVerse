import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { Link } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";
import { authService } from "../services/auth.service";
import { getErrorCode, getErrorMessage } from "../services/api";
import Button from "../components/ui/Button";
import Alert from "../components/ui/Alert";
import { TextInput } from "../components/ui/Field";

/**
 * Password recovery, as four steps in one screen.
 *
 * Deliberately a single page rather than four routes: the intermediate
 * state (the address, and the single-use reset token) has nowhere
 * meaningful to live between navigations, and pushing it into the URL or
 * sessionStorage would widen the number of places a live credential could
 * be read from.
 *
 * No step ever displays the OTP. The code arrives by email; in local
 * development the server logs it, and the developer types it here. Nothing
 * on this screen can reveal a code it was never given.
 */

type Step = "email" | "otp" | "password" | "done";

function formatCountdown(totalSeconds: number): string {
  const clamped = Math.max(0, Math.floor(totalSeconds));
  const minutes = Math.floor(clamped / 60);
  const seconds = clamped % 60;
  return `${minutes}:${String(seconds).padStart(2, "0")}`;
}

export default function ForgotPasswordPage() {
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [otp, setOtp] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [resetToken, setResetToken] = useState("");

  const [notice, setNotice] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});

  // Countdowns, in whole seconds remaining.
  const [cooldown, setCooldown] = useState(0);
  const [expiry, setExpiry] = useState(0);

  // One interval drives both countdowns. The effect depends only on whether
  // a countdown is still running, and the state updates are functional, so a
  // re-render never restarts the timer.
  const countdownRunning = cooldown > 0 || expiry > 0;

  useEffect(() => {
    if (!countdownRunning) return;

    const timer = window.setInterval(() => {
      setCooldown((value) => Math.max(0, value - 1));
      setExpiry((value) => Math.max(0, value - 1));
    }, 1000);

    return () => window.clearInterval(timer);
  }, [countdownRunning]);

  // Once the OTP countdown runs out the code is dead, so say so rather than
  // letting the user keep submitting something that will be refused. Guarded
  // on `expiryEverSet` because zero is also the state before the first
  // response arrives, where there is nothing to have expired yet.
  const expiryEverSet = useRef(false);

  useEffect(() => {
    if (expiry > 0) expiryEverSet.current = true;
  }, [expiry]);

  useEffect(() => {
    if (step === "otp" && expiryEverSet.current && expiry === 0) {
      setNotice("That code expired. Request a new one to continue.");
    }
  }, [expiry, step]);

  const requestOtp = useMutation({
    mutationFn: () => authService.forgotPassword({ email }),
    onSuccess: (response) => {
      setCooldown(response.retry_after_seconds);
      setExpiry(response.expires_in);
      setOtp("");
      setFieldErrors({});
      setStep("otp");
      // The server's wording is deliberately non-committal, and the UI
      // must not be more revealing than it. It never says the account exists.
      setNotice(response.detail);
    },
  });

  const verifyOtp = useMutation({
    mutationFn: () => authService.verifyResetOtp({ email, otp }),
    onSuccess: (response) => {
      setResetToken(response.reset_token);
      setFieldErrors({});
      setNotice(null);
      setStep("password");
    },
  });

  const resetPassword = useMutation({
    mutationFn: () =>
      authService.resetPassword({ reset_token: resetToken, new_password: newPassword }),
    onSuccess: () => {
      setFieldErrors({});
      setStep("done");
    },
  });

  /*
   * Scoped to the current step, not the union of all three mutations.
   * React Query keeps a mutation's `error` until it is reset or the next
   * attempt starts, so a stale failure from the email step would otherwise
   * keep rendering on the OTP and password steps.
   */
  const activeError =
    step === "email"
      ? requestOtp.error
      : step === "otp"
        ? verifyOtp.error
        : resetPassword.error;

  const errorCode = useMemo(() => getErrorCode(activeError), [activeError]);

  /**
   * Maps a machine code to wording that tells the user what to do next.
   *
   * `OTP_ATTEMPTS_EXCEEDED` is also what the server returns when there was
   * never a live code for the address, which is intentional: collapsing the
   * two cases is what stops this endpoint from confirming which emails are
   * registered. Both outcomes need the same advice anyway.
   */
  function friendlyError(fallback: string): string {
    switch (errorCode) {
      case "OTP_ATTEMPTS_EXCEEDED":
        return "Too many incorrect attempts, or no code is active. Request a new code.";
      case "OTP_EXPIRED":
        return "That code has expired. Request a new one.";
      case "OTP_INVALID":
        return "That code is not correct. Check it and try again.";
      case "RESET_TOKEN_INVALID":
        return "This reset session is invalid or already used. Start again.";
      case "RESET_TOKEN_EXPIRED":
        return "This reset session has expired. Start again.";
      default:
        return getErrorMessage(activeError, fallback);
    }
  }

  // --- step 1: email -----------------------------------------------------

  function submitEmail(event: FormEvent) {
    event.preventDefault();
    const trimmed = email.trim();
    if (!trimmed) {
      setFieldErrors({ email: "Enter the email address on your account." });
      return;
    }
    setFieldErrors({});
    setNotice(null);
    // Clear the previous outcome, so a retry does not still show the
    // result of the attempt before it.
    requestOtp.reset();
    requestOtp.mutate();
  }

  // --- step 2: otp -------------------------------------------------------

  function submitOtp(event: FormEvent) {
    event.preventDefault();
    const trimmed = otp.trim();
    if (!trimmed) {
      setFieldErrors({ otp: "Enter the code from your email." });
      return;
    }
    setFieldErrors({});
    setNotice(null);
    verifyOtp.reset();
    verifyOtp.mutate();
  }

  function resend() {
    setNotice(null);
    setFieldErrors({});
    requestOtp.reset();
    requestOtp.mutate();
  }

  function restart() {
    setStep("email");
    setOtp("");
    setNewPassword("");
    setConfirmPassword("");
    setResetToken("");
    setCooldown(0);
    setExpiry(0);
    setNotice(null);
    setFieldErrors({});
    expiryEverSet.current = false;
    requestOtp.reset();
    verifyOtp.reset();
    resetPassword.reset();
  }

  // --- step 3: new password ---------------------------------------------

  function submitPassword(event: FormEvent) {
    event.preventDefault();

    const errors: Record<string, string> = {};
    if (newPassword.length < 6) {
      errors.newPassword = "Use at least 6 characters.";
    } else if (newPassword.length > 72) {
      errors.newPassword = "Use at most 72 characters.";
    }
    if (confirmPassword !== newPassword) {
      errors.confirmPassword = "The two passwords do not match.";
    }

    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setNotice(null);
    resetPassword.reset();
    resetPassword.mutate();
  }

  return (
    <div className="rounded-lg border border-slate-200 bg-white p-6 shadow-sm">
      <h1 className="text-xl font-semibold tracking-tight text-slate-900">
        {step === "done" ? "Password updated" : "Reset your password"}
      </h1>
      <p className="mt-1 text-sm text-slate-500">
        {step === "email" && "We will email you a code to confirm your account."}
        {step === "otp" && `Enter the code sent to ${email}.`}
        {step === "password" && "Choose a new password for your account."}
        {step === "done" && "Your password has been changed. Sign in with it now."}
      </p>

      {/*
        Errors and the notice can both be true at once, and the error wins.
        Suppressing the error whenever a notice happened to be on screen
        left a wrong OTP looking like a successful send: the "we emailed you
        a code" message stayed up and the actual failure was never shown, so
        the user had no idea why nothing was happening.
      */}
      {activeError && (
        <Alert tone="danger" className="mt-4">
          {friendlyError("Could not complete the password reset.")}
        </Alert>
      )}

      {notice && !activeError && (
        <Alert tone={step === "done" ? "success" : "info"} className="mt-4">
          {notice}
        </Alert>
      )}

      {/* Step 1 — email */}
      {step === "email" && (
        <form onSubmit={submitEmail} className="mt-4 space-y-4" noValidate>
          <TextInput
            label="Email address"
            type="email"
            name="email"
            autoComplete="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            error={fieldErrors.email}
            hint="Use the address you registered with."
          />
          <Button type="submit" isLoading={requestOtp.isPending} className="w-full">
            Send code
          </Button>
        </form>
      )}

      {/* Step 2 — OTP */}
      {step === "otp" && (
        <form onSubmit={submitOtp} className="mt-4 space-y-4" noValidate>
          <TextInput
            label="Verification code"
            name="otp"
            type="text"
            inputMode="numeric"
            autoComplete="one-time-code"
            // The OTP field is mounted fresh when this step renders, so the
            // native attribute focuses it at the right moment without the
            // shared TextInput needing to become a forwardRef component.
            autoFocus
            maxLength={8}
            value={otp}
            onChange={(event) => setOtp(event.target.value.replace(/\D/g, ""))}
            error={fieldErrors.otp}
            hint={expiry > 0 ? `This code expires in ${formatCountdown(expiry)}.` : undefined}
          />

          <div className="flex items-center justify-between gap-3 text-sm">
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={resend}
              disabled={cooldown > 0 || requestOtp.isPending}
            >
              {cooldown > 0 ? `Resend in ${formatCountdown(cooldown)}` : "Resend code"}
            </Button>
            <button
              type="button"
              onClick={restart}
              className="text-slate-600 underline underline-offset-2 hover:text-slate-900"
            >
              Use a different email
            </button>
          </div>

          <Button type="submit" isLoading={verifyOtp.isPending} className="w-full">
            Verify code
          </Button>
        </form>
      )}

      {/* Step 3 — new password */}
      {step === "password" && (
        <form onSubmit={submitPassword} className="mt-4 space-y-4" noValidate>
          <TextInput
            label="New password"
            type="password"
            name="new_password"
            autoComplete="new-password"
            value={newPassword}
            onChange={(event) => setNewPassword(event.target.value)}
            error={fieldErrors.newPassword}
            hint="At least 6 characters."
          />
          <TextInput
            label="Confirm new password"
            type="password"
            name="confirm_password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(event) => setConfirmPassword(event.target.value)}
            error={fieldErrors.confirmPassword}
          />
          <Button type="submit" isLoading={resetPassword.isPending} className="w-full">
            Update password
          </Button>
        </form>
      )}

      {step !== "email" && step !== "done" && (
        <p className="mt-4 text-center text-sm">
          <button
            type="button"
            onClick={restart}
            className="text-slate-600 underline underline-offset-2 hover:text-slate-900"
          >
            Start over
          </button>
        </p>
      )}

      <p className="mt-4 text-center text-sm text-slate-600">
        {step === "done" ? (
          <Link to="/login" className="font-medium text-teal-700 underline underline-offset-2">
            Back to sign in
          </Link>
        ) : (
          <>
            Remembered it?{" "}
            <Link to="/login" className="font-medium text-teal-700 underline underline-offset-2">
              Back to sign in
            </Link>
          </>
        )}
      </p>
    </div>
  );
}
