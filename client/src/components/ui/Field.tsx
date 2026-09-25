import { useId } from "react";
import type { InputHTMLAttributes, SelectHTMLAttributes, TextareaHTMLAttributes } from "react";

const FIELD_CLASSES =
  "w-full rounded-md border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 " +
  "placeholder:text-slate-400 focus:border-teal-600 focus:outline-none focus:ring-1 " +
  "focus:ring-teal-600 disabled:bg-slate-50 disabled:text-slate-500";

interface FieldProps {
  label: string;
  hint?: string;
  error?: string;
}

function FieldShell({
  label,
  hint,
  error,
  htmlFor,
  children,
}: FieldProps & { htmlFor: string; children: React.ReactNode }) {
  return (
    <div className="space-y-1">
      <label htmlFor={htmlFor} className="block text-sm font-medium text-slate-700">
        {label}
      </label>
      {children}
      {hint && !error && <p className="text-xs text-slate-500">{hint}</p>}
      {error && (
        <p id={`${htmlFor}-error`} role="alert" className="text-xs text-red-600">
          {error}
        </p>
      )}
    </div>
  );
}

type TextInputProps = FieldProps & InputHTMLAttributes<HTMLInputElement>;

export function TextInput({ label, hint, error, className = "", ...rest }: TextInputProps) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={id}>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`${FIELD_CLASSES} ${error ? "border-red-400" : ""} ${className}`}
        {...rest}
      />
    </FieldShell>
  );
}

type SelectProps = FieldProps & SelectHTMLAttributes<HTMLSelectElement>;

export function Select({ label, hint, error, className = "", children, ...rest }: SelectProps) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={id}>
      <select
        id={id}
        aria-invalid={error ? true : undefined}
        className={`${FIELD_CLASSES} ${error ? "border-red-400" : ""} ${className}`}
        {...rest}
      >
        {children}
      </select>
    </FieldShell>
  );
}

type TextareaProps = FieldProps & TextareaHTMLAttributes<HTMLTextAreaElement>;

export function Textarea({ label, hint, error, className = "", ...rest }: TextareaProps) {
  const id = useId();
  return (
    <FieldShell label={label} hint={hint} error={error} htmlFor={id}>
      <textarea
        id={id}
        aria-invalid={error ? true : undefined}
        className={`${FIELD_CLASSES} min-h-[96px] ${error ? "border-red-400" : ""} ${className}`}
        {...rest}
      />
    </FieldShell>
  );
}
