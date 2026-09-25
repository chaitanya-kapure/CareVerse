interface SpinnerProps {
  label?: string;
  className?: string;
}

/** Busy indicator. Announced to assistive tech via a polite live region. */
export default function Spinner({ label = "Loading", className = "" }: SpinnerProps) {
  return (
    <div
      role="status"
      aria-live="polite"
      className={`flex items-center justify-center gap-3 py-10 text-sm text-slate-500 ${className}`}
    >
      <span
        aria-hidden="true"
        className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-teal-700"
      />
      <span>{label}…</span>
    </div>
  );
}
