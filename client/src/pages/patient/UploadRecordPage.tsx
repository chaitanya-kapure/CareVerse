import { useState, useEffect } from "react";
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

const MAX_UPLOAD_MB = 15;

const CATEGORIES = [
  { value: "lab_report", label: "🧪 Lab report (Blood test, Urine, Pathology)" },
  { value: "prescription", label: "💊 Doctor's Prescription" },
  { value: "discharge_summary", label: "🏥 Hospital Discharge Summary" },
  { value: "imaging", label: "🩻 Imaging Report (X-Ray, MRI, CT, Ultrasound)" },
  { value: "other", label: "📄 Other Medical Document" },
];

export default function UploadRecordPage() {
  const navigate = useNavigate();

  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [title, setTitle] = useState("");
  const [category, setCategory] = useState("lab_report");
  const [documentDate, setDocumentDate] = useState("");
  const [localError, setLocalError] = useState<string | null>(null);
  const [dragging, setDragging] = useState(false);

  useEffect(() => {
    if (file && file.type.startsWith("image/")) {
      const url = URL.createObjectURL(file);
      setPreviewUrl(url);
      return () => URL.revokeObjectURL(url);
    } else {
      setPreviewUrl(null);
    }
  }, [file]);

  const upload = useMutation({
    mutationFn: () =>
      documentService.upload({
        file: file as File,
        title,
        category,
        document_date: documentDate || undefined,
      }),
    onSuccess: (created) => navigate(`/patient/records/${created.id}`),
  });

  const choose = (candidate: File | undefined | null) => {
    if (!candidate) return;
    setLocalError(null);
    upload.reset();

    const fileNameLower = candidate.name.toLowerCase();
    const isPdf =
      candidate.type === "application/pdf" || fileNameLower.endsWith(".pdf");
    const isImage =
      candidate.type.startsWith("image/") ||
      fileNameLower.endsWith(".jpg") ||
      fileNameLower.endsWith(".jpeg") ||
      fileNameLower.endsWith(".png") ||
      fileNameLower.endsWith(".webp");

    if (!isPdf && !isImage) {
      setLocalError(
        "Supported file types: PDF documents and images (JPG, PNG, WebP). Please select a valid document.",
      );
      return;
    }
    if (candidate.size > MAX_UPLOAD_MB * 1024 * 1024) {
      setLocalError(
        `That file is ${formatBytes(candidate.size)}. The limit is ${MAX_UPLOAD_MB} MB. Please upload a smaller file.`,
      );
      return;
    }

    setFile(candidate);
    if (!title.trim()) {
      const cleanTitle = candidate.name.replace(/\.(pdf|jpe?g|png|webp)$/i, "");
      setTitle(cleanTitle);
    }
  };

  const onSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setLocalError(null);
    if (!file) {
      setLocalError("Please select a document or photo to upload.");
      return;
    }
    upload.mutate();
  };

  const error = localError ?? (upload.error ? getErrorMessage(upload.error) : null);

  return (
    <>
      <PageHeader
        title="Upload Medical Document"
        description="Add your lab reports, doctor prescriptions, or discharge summaries. PDF documents and camera photos (JPG/PNG) are supported with automatic OCR text extraction."
      />

      {error && (
        <Alert tone="danger" title="Upload could not proceed" className="mb-4">
          {error}
        </Alert>
      )}

      <form onSubmit={onSubmit} noValidate>
        <div className="grid gap-6 lg:grid-cols-2">
          {/* File Picker Card */}
          <Card
            title="1. Select Document or Photo"
            description="Drag and drop or browse from your device."
          >
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
              className={`flex flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed p-6 text-center transition-all ${
                dragging
                  ? "border-teal-600 bg-teal-50"
                  : "border-slate-300 bg-slate-50 hover:bg-slate-100/70"
              }`}
            >
              <div className="flex h-12 w-12 items-center justify-center rounded-full bg-teal-100 text-teal-700">
                <svg
                  xmlns="http://www.w3.org/2000/svg"
                  className="h-6 w-6"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12"
                  />
                </svg>
              </div>

              <div>
                <label className="cursor-pointer">
                  <input
                    type="file"
                    accept="application/pdf,image/jpeg,image/png,image/webp,.pdf,.jpg,.jpeg,.png,.webp"
                    className="sr-only"
                    onChange={(event) => {
                      const picked = event.target.files?.[0];
                      event.target.value = "";
                      choose(picked);
                    }}
                  />
                  <span className="rounded-md bg-teal-700 px-4 py-2 text-sm font-semibold text-white shadow-sm hover:bg-teal-800 transition-colors">
                    Browse File or Photo
                  </span>
                </label>
                <p className="mt-2 text-xs text-slate-500">
                  Drag & drop PDF, JPG, or PNG up to {MAX_UPLOAD_MB} MB
                </p>
              </div>

              {/* Selected File / Preview Box */}
              {file && (
                <div className="mt-3 w-full rounded-lg border border-teal-200 bg-white p-3 text-left shadow-sm">
                  <div className="flex items-center gap-3">
                    {previewUrl ? (
                      <img
                        src={previewUrl}
                        alt="Document Preview"
                        className="h-16 w-16 rounded object-cover border border-slate-200"
                      />
                    ) : (
                      <div className="flex h-12 w-12 shrink-0 items-center justify-center rounded bg-red-50 text-red-600 font-bold text-xs uppercase">
                        PDF
                      </div>
                    )}
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-semibold text-slate-900">
                        {file.name}
                      </p>
                      <p className="text-xs text-slate-500">
                        {formatBytes(file.size)} • Ready for OCR extraction
                      </p>
                    </div>
                    <button
                      type="button"
                      onClick={() => setFile(null)}
                      className="text-xs font-medium text-slate-400 hover:text-red-600"
                    >
                      Remove
                    </button>
                  </div>
                </div>
              )}
            </div>

            <div className="mt-6 flex items-center gap-4">
              <Button type="submit" isLoading={upload.isPending} disabled={!file} size="lg">
                {upload.isPending ? "Uploading & Extracting..." : "Upload & Analyze Record"}
              </Button>
              <Link
                to="/patient/records"
                className="text-sm font-medium text-slate-600 hover:text-slate-900"
              >
                Cancel
              </Link>
            </div>

            {upload.isPending && (
              <div className="mt-4 rounded-md bg-teal-50 p-3 text-sm text-teal-800 flex items-center gap-2">
                <span className="inline-block h-3 w-3 animate-ping rounded-full bg-teal-600" />
                <span>
                  Uploading file, performing OCR text extraction, and parsing clinical
                  data... Please wait a moment.
                </span>
              </div>
            )}
          </Card>

          {/* Details & Help Card */}
          <div className="space-y-6">
            <Card
              title="2. Document Details"
              description="Helpful information to organize your medical history."
            >
              <div className="space-y-4">
                <TextInput
                  label="Document Title"
                  value={title}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="e.g. Complete Blood Count (CBC) - June 2026"
                  maxLength={200}
                  hint="Left blank, the file name will be used automatically."
                />

                <Select
                  label="Document Category"
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
                  label="Date on the Document (Optional)"
                  type="date"
                  value={documentDate}
                  onChange={(event) => setDocumentDate(event.target.value)}
                  hint="If known, enter the date printed on the report."
                />
              </div>
            </Card>

            <Card title="How CareVerse Handles Your Records">
              <ul className="space-y-2.5 text-xs text-slate-600">
                <li className="flex items-start gap-2">
                  <span className="text-teal-600 font-bold">✓</span>
                  <span>
                    <strong>Smart OCR & Extraction:</strong> Scanned reports, photos, and digital
                    PDFs are automatically scanned for test results, medications, and dates.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-teal-600 font-bold">✓</span>
                  <span>
                    <strong>Safe & Private:</strong> Your original files are stored securely and
                    remain 100% private. Only doctors you explicitly authorize can ever see them.
                  </span>
                </li>
                <li className="flex items-start gap-2">
                  <span className="text-teal-600 font-bold">✓</span>
                  <span>
                    <strong>No Medical Guesswork:</strong> CareVerse extracts what is written on
                    the document and never invents or guesses findings.
                  </span>
                </li>
              </ul>
            </Card>
          </div>
        </div>
      </form>
    </>
  );
}
