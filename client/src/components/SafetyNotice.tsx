import { NOT_A_DIAGNOSIS_NOTICE } from "../utils/disclaimers";

/**
 * Persistent reminder that CAREVERSE summarizes records and does not
 * diagnose. Small by design -- it is information density, not a hero
 * banner, so it does not compete with the clinical content around it.
 */
export default function SafetyNotice({ className = "" }: { className?: string }) {
  return (
    <p className={`text-xs leading-relaxed text-slate-500 ${className}`}>
      <span className="font-medium text-slate-600">Not medical advice.</span>{" "}
      {NOT_A_DIAGNOSIS_NOTICE}
    </p>
  );
}
