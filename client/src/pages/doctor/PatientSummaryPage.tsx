import PhasePlaceholder from "../../components/PhasePlaceholder";

/**
 * The AI summary is not built.
 *
 * Phase 3 delivered doctor access to records; the summary is deliberately
 * later, because summarizing is a different feature from authorizing and
 * storing. This route exists so the URL is not a dead end, and the
 * placeholder says plainly that nothing is generated here -- a doctor cannot
 * be shown a screen implying a summary exists when none does.
 */
export default function PatientSummaryPage() {
  return (
    <PhasePlaceholder
      title="Patient Summary"
      description="An AI-generated, source-linked summary of a patient's records. Not built yet."
      phase="Phase 4"
    />
  );
}
