import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useAuth } from "../hooks/useAuth";
import { NAV_BY_ROLE } from "../utils/navigation";
import Button from "../components/ui/Button";
import SafetyNotice from "../components/SafetyNotice";
import type { UserRole } from "../types";

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return [
    "block rounded-md px-3 py-2 text-sm font-medium transition-colors",
    isActive
      ? "bg-teal-50 text-teal-800"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  ].join(" ");
}

function Sidebar({ role }: { role: UserRole }) {
  const items = NAV_BY_ROLE[role];
  return (
    <nav aria-label="Main" className="flex-1 space-y-1 px-3">
      {items.map((item) => (
        <NavLink
          key={item.to}
          to={item.to}
          end={item.end}
          className={navLinkClasses}
        >
          {item.label}
        </NavLink>
      ))}
    </nav>
  );
}

function Topbar() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-slate-900">{user?.name}</p>
        <p className="truncate text-xs capitalize text-slate-500">
          {user?.role} portal
        </p>
      </div>
      <Button variant="secondary" size="sm" onClick={handleLogout}>
        Sign out
      </Button>
    </header>
  );
}

/** Shell for every signed-in screen: sidebar, topbar, content area. */
export default function AppShell() {
  const { user } = useAuth();
  // RequireAuth guarantees a user before this renders; the fallback keeps
  // the type non-nullable without an unsafe cast.
  const role: UserRole = user?.role ?? "patient";

  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>

      <div className="flex min-h-screen flex-col md:flex-row">
        <aside className="border-b border-slate-200 bg-white md:w-60 md:shrink-0 md:border-b-0 md:border-r">
          <div className="flex items-center gap-2 px-3 py-4 md:px-4">
            <span className="flex h-7 w-7 items-center justify-center rounded bg-teal-700 text-sm font-bold text-white">
              C
            </span>
            <div>
              <p className="text-sm font-semibold tracking-tight text-slate-900">CAREVERSE</p>
              <p className="text-xs text-slate-500">{role} portal</p>
            </div>
          </div>
          <div className="pb-4 md:flex md:flex-col md:pb-6">
            <Sidebar role={role} />
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar />
          <main id="main-content" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-6xl">
              <Outlet />
              <SafetyNotice className="mt-8" />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
