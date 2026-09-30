interface DetailRowProps {
  label: string;
  value: string | number | null | undefined;
  /** Shown when the value is absent. Distinct from the value being `-`. */
  empty?: string;
}

/**
 * One label/value line inside a `<dl>`.
 *
 * Shared so a profile field reads identically wherever it appears -- on the
 * patient's own profile, and on the profile an authorized doctor sees. The
 * `empty` fallback is explicit because "not recorded" and a recorded value
 * are different facts, and a screen that renders both as a dash erases that.
 */
export default function DetailRow({ label, value, empty = "-" }: DetailRowProps) {
  const display = value === null || value === undefined || value === "" ? empty : value;
  return (
    <div className="flex items-baseline justify-between gap-4 py-2">
      <dt className="text-slate-500">{label}</dt>
      <dd className="truncate text-right font-medium text-slate-900">{display}</dd>
    </div>
  );
}
