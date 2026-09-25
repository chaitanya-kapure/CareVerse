import { Link, Outlet } from "react-router-dom";
import SafetyNotice from "../components/SafetyNotice";

/** Centered shell for the public sign-in / sign-up screens. */
export default function AuthLayout() {
  return (
    <div className="flex min-h-screen flex-col bg-slate-50">
      <header className="px-6 py-5">
        <Link to="/" className="inline-flex items-center gap-2">
          <span className="flex h-7 w-7 items-center justify-center rounded bg-teal-700 text-sm font-bold text-white">
            C
          </span>
          <span className="text-lg font-semibold tracking-tight text-slate-900">CAREVERSE</span>
        </Link>
      </header>

      <main className="flex flex-1 items-start justify-center px-4 pb-12">
        <div className="w-full max-w-md">
          <Outlet />
        </div>
      </main>

      <footer className="px-6 py-5">
        <SafetyNotice className="mx-auto max-w-md text-center" />
      </footer>
    </div>
  );
}
