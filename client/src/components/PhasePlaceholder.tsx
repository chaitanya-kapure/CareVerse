import PageHeader from "./ui/PageHeader";
import EmptyState from "./ui/EmptyState";

interface PhasePlaceholderProps {
  title: string;
  description: string;
  phase: string;
}

/**
 * Temporary body for screens that are specified but not built yet.
 *
 * It states plainly which phase delivers the screen instead of shipping a
 * fake UI, so nobody mistakes a stub for a working feature during a demo.
 * Each file is replaced as its phase lands.
 */
export default function PhasePlaceholder({ title, description, phase }: PhasePlaceholderProps) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState
        title={`This screen is scheduled for ${phase}`}
        description="The route is wired up and the navigation is live, but the data it depends on does not exist yet."
      />
    </>
  );
}
