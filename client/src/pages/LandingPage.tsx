import { Link } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { dashboardPathFor } from "../utils/navigation";
import Button from "../components/ui/Button";
import Spinner from "../components/ui/Spinner";
import { NOT_A_DIAGNOSIS_NOTICE } from "../utils/disclaimers";

const STEPS = [
  {
    title: "Upload your records",
    body: "Keep lab reports, prescriptions and discharge summaries as PDFs in one place instead of scattered across folders and email threads.",
  },
  {
    title: "CAREVERSE reads them",
    body: "Text and structured fields are extracted from each document and filed against your profile, with the original file always kept intact.",
  },
  {
    title: "Your doctor reviews a summary",
    body: "An authorized doctor sees a concise, source-linked overview of your available history, then opens the original documents to verify anything that matters.",
  },
];

export default function LandingPage() {
  const { status, user } = useAuth();

  return (
    <div className="min-h-screen bg-slate-50">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <div className="flex items-center gap-2">
            <span className="flex h-8 w-8 items-center justify-center rounded bg-teal-700 font-bold text-white">
              C
            </span>
            <span className="text-lg font-semibold tracking-tight text-slate-900">CAREVERSE</span>
          </div>
          <nav className="flex items-center gap-2">
            {status === "loading" ? (
              <Spinner label="" className="py-0" />
            ) : user ? (
              <Link to={dashboardPathFor(user.role)}>
                <Button size="sm">Go to dashboard</Button>
              </Link>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost" size="sm">
                    Sign in
                  </Button>
                </Link>
                <Link to="/register">
                  <Button size="sm">Create account</Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-16">
        <div className="max-w-2xl">
          <h1 className="text-3xl font-semibold tracking-tight text-slate-900 sm:text-4xl">
            One patient profile, instead of a folder full of PDFs.
          </h1>
          <p className="mt-4 text-lg text-slate-600">
            CAREVERSE centralizes the medical documents a patient has already uploaded, and
            turns them into a concise summary a doctor can review in seconds — with every claim
            traceable back to the original record.
          </p>
          <div className="mt-8 flex flex-wrap gap-3">
            {status === "unauthenticated" && (
              <>
                <Link to="/register">
                  <Button>Create a patient account</Button>
                </Link>
                <Link to="/register">
                  <Button variant="secondary">Register as a doctor</Button>
                </Link>
              </>
            )}
            {status === "authenticated" && user && (
              <Link to={dashboardPathFor(user.role)}>
                <Button>Continue to your dashboard</Button>
              </Link>
            )}
          </div>
        </div>

        <section aria-labelledby="how-it-works" className="mt-16">
          <h2 id="how-it-works" className="text-lg font-semibold text-slate-900">
            How it works
          </h2>
          <ol className="mt-6 grid gap-4 md:grid-cols-3">
            {STEPS.map((step, index) => (
              <li
                key={step.title}
                className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm"
              >
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-teal-50 text-sm font-semibold text-teal-800">
                  {index + 1}
                </span>
                <h3 className="mt-3 font-medium text-slate-900">{step.title}</h3>
                <p className="mt-1.5 text-sm leading-relaxed text-slate-600">{step.body}</p>
              </li>
            ))}
          </ol>
        </section>

        <section
          aria-labelledby="safety-heading"
          className="mt-12 rounded-lg border border-amber-200 bg-amber-50 p-5"
        >
          <h2 id="safety-heading" className="text-sm font-semibold text-amber-900">
            What CAREVERSE does not do
          </h2>
          <p className="mt-2 text-sm leading-relaxed text-amber-900">
            {NOT_A_DIAGNOSIS_NOTICE} CAREVERSE does not predict conditions, recommend
            treatment or medication, or check for drug interactions. It summarizes documents that
            already exist and leaves every clinical judgement to a qualified professional.
          </p>
        </section>
      </main>

      <footer className="border-t border-slate-200 bg-white">
        <div className="mx-auto max-w-6xl px-6 py-6 text-sm text-slate-500">
          CAREVERSE — hackathon MVP. PDF uploads only.
        </div>
      </footer>
    </div>
  );
}
