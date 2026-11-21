import { FolderKanban, LayoutDashboard, LogOut, Menu, X } from "lucide-react";
import { Suspense, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";
import { useAuth } from "@/auth/AuthContext";
import { FullPageSpinner } from "@/components/ui/Spinner";
import { cn } from "@/lib/cn";
import { Logo } from "./Logo";

const nav = [
  { to: "/app", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "/app/projects", label: "Projects", icon: FolderKanban, end: false },
];

function Sidebar({ onNavigate }: { onNavigate?: () => void }) {
  const { user, logout } = useAuth();
  const initials = (user?.displayName ?? user?.email ?? "?").split(/\s+/).map((p) => p[0]).join("").slice(0, 2).toUpperCase();
  return (
    <div className="flex h-full flex-col">
      <div className="flex h-16 items-center px-5">
        <Logo to="/app" />
      </div>
      <nav className="flex-1 space-y-1 px-3 py-2" aria-label="Main">
        {nav.map(({ to, label, icon: Icon, end }) => (
          <NavLink key={to} to={to} end={end} onClick={onNavigate}
            className={({ isActive }) => cn("group flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors",
              isActive ? "bg-accent-500/10 text-ink-100 shadow-[inset_2px_0_0_0_var(--color-accent-400)]" : "text-ink-300 hover:bg-ink-800 hover:text-ink-100")}>
            <Icon className="size-4 shrink-0" />
            {label}
          </NavLink>
        ))}
      </nav>
      <div className="border-t border-ink-700/60 p-3">
        <div className="flex items-center gap-3 rounded-lg px-2 py-2">
          <div className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-accent-500 to-indigo-600 text-xs font-semibold text-white">
            {initials}
          </div>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm text-ink-100">{user?.displayName}</p>
            <p className="truncate text-xs text-ink-400">{user?.email}</p>
          </div>
          <button type="button" onClick={logout} title="Sign out" aria-label="Sign out"
            className="rounded-md p-1.5 text-ink-300 hover:bg-ink-700 hover:text-ink-100">
            <LogOut className="size-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

export function AppShell() {
  const [open, setOpen] = useState(false);
  const location = useLocation();
  return (
    <div className="min-h-screen bg-ink-950">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 border-r border-ink-700/60 bg-ink-900/70 backdrop-blur lg:block">
        <Sidebar />
      </aside>
      {open ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="absolute inset-0 bg-ink-950/70 backdrop-blur-sm" onClick={() => setOpen(false)} aria-hidden="true" />
          <aside className="absolute inset-y-0 left-0 w-72 animate-fade-in border-r border-ink-700 bg-ink-900">
            <button type="button" className="absolute right-3 top-4 rounded-md p-1.5 text-ink-300 hover:bg-ink-700" onClick={() => setOpen(false)} aria-label="Close menu">
              <X className="size-4" />
            </button>
            <Sidebar onNavigate={() => setOpen(false)} />
          </aside>
        </div>
      ) : null}
      <div className="lg:pl-64">
        <div className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-ink-700/60 bg-ink-950/80 px-4 backdrop-blur lg:hidden">
          <button type="button" onClick={() => setOpen(true)} className="rounded-md p-1.5 text-ink-200 hover:bg-ink-800" aria-label="Open menu">
            <Menu className="size-5" />
          </button>
          <Logo to="/app" />
        </div>
        <main key={location.pathname} className="mx-auto max-w-7xl animate-fade-in px-4 py-6 sm:px-6 lg:px-10 lg:py-10">
          <Suspense fallback={<FullPageSpinner label="Loading" />}><Outlet /></Suspense>
        </main>
      </div>
    </div>
  );
}
