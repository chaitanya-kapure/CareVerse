import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useMutation } from "@tanstack/react-query";

import PageHeader from "../../components/ui/PageHeader";
import Card from "../../components/ui/Card";
import Alert from "../../components/ui/Alert";
import Button from "../../components/ui/Button";
import { Select, TextInput } from "../../components/ui/Field";
import { documentService } from "../../services/document.service";
import { getErrorMessage } from "../../services/api";
import { formatBytes } from "../../utils/format";

/**
 * Client-side copy of the server's `MAX_UPLOAD_MB` (see
 * `server/.env.example`). It exists only to save a patient on a slow
 * connection from uploading 40 MB that the server will refuse anyway --
 * the server re-checks the real size and its message is authoritative if
 * the two ever disagree.
 */
const MAX_UPLOAD_MB = 15;

const CATEGORIES = [
  { value: "lab_report", label: "Lab report" },
  { value: "prescription", label: "Prescription" },
  { value: "discharge_summary", label: "Discharge summary" },
  { value: "imaging", label: "Imaging" },
  { value: "other", label: "Something else" },
];

export default function UploadRecordPage() {
  const navigate = useNavigate();

  const [file, setFile] = useState<File | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("other");
  const [documentDate, setDocumentDate] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  const upload = useMutation({
    mutationFn: () =>
      documentService.upload({
        file: file as File,
        title,
        category,
        document_date: documentDate || undefined,
      }),
    // Land on the finished record rather than a toast: the patient's next
    // question is always "did it read my report?".
    onSuccess: (created) => navigate(`/patient/records/${created.id}`),
  });

  /** Rejects the obvious cases here so they are explained, not just failed. */
  const choose = (candidate: File | undefined | null) => {
    if (!candidate) return;
    setLocalError(null);
    upload.reset();

    const looksLikePdf =
      candidate.type === "application/pdf" ||
      candidate.name.toLowerCase().endsWith(".pdf");

    if (!looksLikePdf) {
      setLocalError(
        "Only PDF files can be uploaded. Export your document as a PDF and try again.",
      );
      return;
    }
    if (candidate.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setLocalError(
        `That file is ${formatBytes(candidate.size)}. The limit is ${MAX_UPLOAD_MB} MB -- ` +
          "try exporting a smaller range of pages.",
      );
      return;
    }

    setFile(candidate);
    if (!title.trim()) setTitle(candidate.name.replace(/\.pdf$/i, ""));
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    if (!file) {
      setLocalError("Choose a PDF to upload first.");
      return;
    }
    upload.mutate();
  };

  const error = localError ?? (upload.error ? getErrorMessage(upload.error) : null);

  return (
    <>
      <PageHeader
        title="Upload a medical record"
        description="PDF reports, prescriptions and discharge summaries. Your file is stored once and its text is extracted automatically."
      />

      {error && (
        <Alert tone="danger" title="The upload did not go through" className="mb-4">
          {error}
        </Alert>
      )}

      <form onSubmit={onSubmit} noValidate>
        <div className="grid gap-4 lg:grid-cols-2">
          <Card title="Choose a PDF" description="Drag one in, or select it.">
            <div
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDragLeave={() => setDragging(false)}
              onDrop={(event) => {
                event.preventDefault();
                setDragging(false);
                choose(event.dataTransfer.files?.[0]);
              }}
              className={`flex flex-col items-center justify-center gap-2 rounded-md border-2 border-dashed px-4 py-8 text-center transition-colors ${
                dragging ? "border-teal-600 bg-teal-50" : "border-slate-300 bg-slate-50"
              }`}
            >
              <label className="cursor-pointer text-center">
                <input
                  type="file"
                  accept="application/pdf,.pdf"
                  className="sr-only"
                  onChange={(event) => {
                    const picked = event.target.files?.[0];
                    // Cleared so the same file can be selected again after a
                    // rejection -- otherwise a fixed-but-identical file fires
                    // no change event and the patient gets no feedback.
                    event.target.value = "";
                    choose(picked);
                  }}
                />
                <span className="text-sm font-medium text-teal-700 hover:underline">
                  Select a PDF
                </span>
              </label>
              <p className="text-xs text-slate-500">
                or drop one here - up to {MAX_UPLOAD_MB} MB
              </p>

              {file && (
                <div className="mt-2 w-full rounded-md border border-slate-200 bg-white px-3 py-2 text-left">
                  <p className="truncate text-sm font-medium text-slate-900">{file.name}</p>
                  <p className="text-xs text-slate-500">{formatBytes(file.size)}</p>
                </div>
              )}
            </div>

            <div className="mt-4 flex items-center gap-3">
              <Button type="submit" isLoading={upload.isPending} disabled={!file}>
                {upload.isPending ? "Uploading..." : "Upload record"}
              </Button>
              <Link
                to="/patient/records"
                className="text-sm font-medium text-teal-700 hover:underline"
              >
                Cancel
              </Link>
            </div>

            {upload.isPending && (
              <p className="mt-3 text-sm text-slate-500" aria-live="polite">
                Uploading and extracting text. A large or scanned document can take a
                moment.
              </p>
            )}
          </Card>

          <Card
            title="Optional details"
            description="Helps you find this record later. None of it is read from the file."
          >
            <div className="space-y-4">
              <TextInput
                label="Title"
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="CBC report - June"
                maxLength={200}
                hint="Left blank, the filename is used."
              />
              <Select
                label="What kind of document is this?"
                value={category}
                onChange={(event) => setCategory(event.target.value)}
              >
                {CATEGORIES.map((option) => (
                  <option key={option.value} value={option.value}>
                    {option.label}
                  </option>
                ))}
              </Select>
              <TextInput
                label="Date on the document"
                type="date"
                value={documentDate}
                onChange={(event) => setDocumentDate(event.target.value)}
                hint="Optional. Type it exactly as printed on the report."
              />
            </div>

            <p className="mt-4 text-xs leading-relaxed text-slate-500">
              The original PDF is always kept. If a document is a scan with no readable
              text, CAREVERSE records that it needs OCR rather than guessing at what it
              says.
            </p>
          </Card>
        </div>
      </form>
    </>
  );
}
