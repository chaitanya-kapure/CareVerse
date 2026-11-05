import { Link } from "react-router-dom";

import Card from "./ui/Card";
import type { SummarySection } from "../types";
import { EMPTY_SECTION_NOTE } from "../utils/disclaimers";

interface SummarySectionCardProps {
  section: SummarySection;
   /** Where one of this section's source documents lives, for the audience */
  documentHref: (documentId: string) => string;
}

 /** One summary section: its items, or an explicit statement that it found */
export default function SummarySectionCard({
  section,
  documentHref,
}: SummarySectionCardProps) {
  const isEmpty = section.items.length === 0;
  const note = section.empty_note ?? EMPTY_SECTION_NOTE;
  const count = section.items.length;

  return (
    <Card
      title={section.title}
      description={
        isEmpty
          ? undefined
          : count === 1
            ? "1 item, copied from a record."
            : `${count} items, each copied from a record.`
      }
    >
      {isEmpty ? (
        <p className="text-sm italic text-slate-500">{note}</p>
      ) : (
        <ul className="divide-y divide-slate-100">
          {section.items.map((item, index) => (
            <li key={`${section.key}-${item.source_document_id}-${index}`} className="py-2.5">
              <p className="text-sm text-slate-800">{item.text}</p>
              <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs text-slate-500">
                {item.source_text && (
                  <span className="italic">
                    On the document: &ldquo;{item.source_text}&rdquo;
                  </span>
                )}
                <Link
                  to={documentHref(item.source_document_id)}
                  className="font-medium text-teal-700 underline underline-offset-2 hover:text-teal-900"
                >
                  View source record
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}
