import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuth } from "../hooks/useAuth";
import { NAV_BY_ROLE, type NavItem } from "../utils/navigation";
import { notificationService } from "../services/notification.service";
import Button from "../components/ui/Button";
import ThemeToggle from "../components/ui/ThemeToggle";
import SafetyNotice from "../components/SafetyNotice";
import type { UserRole } from "../types";

function navLinkClasses({ isActive }: { isActive: boolean }): string {
  return [
    "flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all",
    isActive
      ? "bg-teal-700 text-white shadow-sm"
      : "text-slate-600 hover:bg-slate-100 hover:text-slate-900",
  ].join(" ");
}

function SidebarNav({
  role,
  onNavigate,
}: {
  role: UserRole;
  onNavigate?: () => void;
}) {
  const items = NAV_BY_ROLE[role];
  const { data } = useQuery({
    queryKey: ["notif-unread-count"],
    queryFn: notificationService.unreadCount,
    refetchInterval: 30_000,
  });
  const unread = data?.count ?? 0;

  const coreItems = items.filter((i) => i.section === "core");
  const connectItems = items.filter((i) => i.section === "connect");
  const accountItems = items.filter((i) => i.section === "account");

  const renderSection = (title: string, sectionItems: NavItem[]) => (
    <div className="mb-4">
      <p className="px-3 mb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-400">
        {title}
      </p>
      <div className="space-y-1">
        {sectionItems.map((item) => (
          <NavLink
            key={item.to}
            to={item.to}
            end={item.end}
            onClick={onNavigate}
            className={navLinkClasses}
          >
            <span className="text-base leading-none" aria-hidden="true">
              {item.icon}
            </span>
            <span className="flex-1 truncate">{item.label}</span>
            {item.label === "Notifications" && unread > 0 && (
              <span className="ml-auto flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-red-500 px-1 text-xs font-bold text-white">
                {unread > 99 ? "99+" : unread}
              </span>
            )}
          </NavLink>
        ))}
      </div>
    </div>
  );

  return (
    <nav aria-label="Main" className="flex-1 px-3 py-2">
      {renderSection(role === "patient" ? "Health Vault" : "Clinical Core", coreItems)}
      {renderSection("Doctors & Network", connectItems)}
      {renderSection("Account", accountItems)}
    </nav>
  );
}

function Topbar({ onToggleMenu }: { onToggleMenu: () => void }) {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login", { replace: true });
  };

  return (
    <header className="sticky top-0 z-20 flex items-center justify-between gap-4 border-b border-slate-200 bg-white px-4 py-3 sm:px-6">
      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleMenu}
          className="flex h-9 w-9 items-center justify-center rounded-lg border border-slate-200 text-slate-600 md:hidden hover:bg-slate-50"
          aria-label="Toggle navigation menu"
        >
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>

        <div className="min-w-0">
          <p className="truncate text-sm font-semibold text-slate-900">{user?.name}</p>
          <p className="truncate text-xs capitalize text-slate-500">
            {user?.role} Portal
          </p>
        </div>
      </div>

      <div className="flex items-center gap-2">
        <ThemeToggle />
        <Button variant="secondary" size="sm" onClick={handleLogout}>
          Sign out
        </Button>
      </div>
    </header>
  );
}

/** Shell for every signed-in screen: sidebar, topbar, content area. */
export default function AppShell() {
  const { user } = useAuth();
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const role: UserRole = user?.role ?? "patient";

  return (
    <div className="min-h-screen bg-slate-50">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded focus:bg-white focus:px-3 focus:py-2 focus:shadow"
      >
        Skip to main content
      </a>

      <div className="flex min-h-screen">
        {/* Desktop Sidebar */}
        <aside className="hidden border-r border-slate-200 bg-white md:flex md:w-64 md:shrink-0 md:flex-col">
          <div className="flex items-center gap-2.5 px-5 py-4 border-b border-slate-100">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-700 text-base font-bold text-white shadow-sm">
              C
            </span>
            <div>
              <p className="text-base font-bold tracking-tight text-slate-900">CAREVERSE</p>
              <p className="text-[11px] font-medium uppercase tracking-wider text-teal-700">
                {role} Portal
              </p>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto py-3">
            <SidebarNav role={role} />
          </div>
        </aside>

        {/* Mobile Drawer Backdrop & Sidebar */}
        {mobileMenuOpen && (
          <div className="fixed inset-0 z-40 md:hidden">
            <div
              className="fixed inset-0 bg-slate-900/50 backdrop-blur-sm transition-opacity"
              onClick={() => setMobileMenuOpen(false)}
            />
            <div className="fixed inset-y-0 left-0 z-50 flex w-72 flex-col bg-white shadow-xl">
              <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
                <div className="flex items-center gap-2.5">
                  <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-teal-700 text-base font-bold text-white">
                    C
                  </span>
                  <div>
                    <p className="text-base font-bold text-slate-900">CAREVERSE</p>
                    <p className="text-[11px] uppercase tracking-wider text-teal-700">{role} Portal</p>
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setMobileMenuOpen(false)}
                  className="rounded-lg p-1 text-slate-400 hover:text-slate-600"
                >
                  ✕
                </button>
              </div>
              <div className="flex-1 overflow-y-auto py-3">
                <SidebarNav role={role} onNavigate={() => setMobileMenuOpen(false)} />
              </div>
            </div>
          </div>
        )}

        {/* Main Content Area */}
        <div className="flex min-w-0 flex-1 flex-col">
          <Topbar onToggleMenu={() => setMobileMenuOpen(!mobileMenuOpen)} />
          <main id="main-content" className="flex-1 px-4 py-6 sm:px-6 lg:px-8">
            <div className="mx-auto w-full max-w-6xl">
              <Outlet />
              <SafetyNotice className="mt-10" />
            </div>
          </main>
        </div>
      </div>
    </div>
  );
}
