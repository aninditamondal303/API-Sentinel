import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { lazy, Suspense, useState, type ReactNode } from "react";
import { BrowserRouter, Link, Route, Routes } from "react-router";
import { ApiError } from "@/api/client";
import { AuthProvider } from "@/auth/AuthContext";
import { RedirectIfAuthenticated, RequireAuth } from "@/auth/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { FullPageSpinner } from "@/components/ui/Spinner";
import { ToastProvider } from "@/components/ui/Toast";
import { LoginPage } from "@/features/auth/LoginPage";
import { RegisterPage } from "@/features/auth/RegisterPage";
import { LandingPage } from "@/features/landing/LandingPage";

// Signed-in pages (and the charting library) load on demand, keeping the landing page light.
const pages = {
  dashboard: () => import("@/features/dashboard/DashboardPage").then((m) => ({ default: m.DashboardPage })),
  projects: () => import("@/features/projects/ProjectsPage").then((m) => ({ default: m.ProjectsPage })),
  projectDetail: () => import("@/features/projects/ProjectDetailPage").then((m) => ({ default: m.ProjectDetailPage })),
  compare: () => import("@/features/scans/ComparePage").then((m) => ({ default: m.ComparePage })),
  scanDetail: () => import("@/features/scans/ScanDetailPage").then((m) => ({ default: m.ScanDetailPage })),
  specDetail: () => import("@/features/specifications/SpecDetailPage").then((m) => ({ default: m.SpecDetailPage })),
};
const DashboardPage = lazy(pages.dashboard);
const ProjectsPage = lazy(pages.projects);
const ProjectDetailPage = lazy(pages.projectDetail);
const ComparePage = lazy(pages.compare);
const ScanDetailPage = lazy(pages.scanDetail);
const SpecDetailPage = lazy(pages.specDetail);

/** Loads every signed-in page chunk (module imports are cached, so lazy() then resolves immediately). */
export function preloadAppPages(): Promise<unknown> {
  return Promise.all(Object.values(pages).map((load) => load()));
}

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 15_000,
        refetchOnWindowFocus: false,
        // Client errors (401/403/404/422...) will not change on retry; transient server errors might.
        retry: (count, error) => count < 2 && !(error instanceof ApiError && error.status >= 400 && error.status < 500),
      },
      mutations: { retry: false },
    },
  });
}

export function NotFound({ home = "/" }: { home?: string }) {
  return (
    <div className="flex min-h-[60vh] flex-col items-center justify-center text-center">
      <p className="font-mono text-sm text-accent-400">404</p>
      <h1 className="mt-2 text-2xl font-semibold">Page not found</h1>
      <p className="mt-2 text-sm text-ink-300">The page you are looking for does not exist.</p>
      <Link to={home} className="mt-6 text-sm font-medium text-accent-300 hover:text-accent-200">{home === "/" ? "Back to home" : "Back to dashboard"}</Link>
    </div>
  );
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<LandingPage />} />
      <Route path="/login" element={<RedirectIfAuthenticated><LoginPage /></RedirectIfAuthenticated>} />
      <Route path="/register" element={<RedirectIfAuthenticated><RegisterPage /></RedirectIfAuthenticated>} />
      <Route path="/app" element={<RequireAuth><Suspense fallback={<FullPageSpinner label="Loading" />}><AppShell /></Suspense></RequireAuth>}>
        <Route index element={<DashboardPage />} />
        <Route path="projects" element={<ProjectsPage />} />
        <Route path="projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="projects/:projectId/compare" element={<ComparePage />} />
        <Route path="projects/:projectId/specifications/:specId" element={<SpecDetailPage />} />
        <Route path="projects/:projectId/scans/:scanId" element={<ScanDetailPage />} />
        <Route path="*" element={<NotFound home="/app" />} />
      </Route>
      <Route path="*" element={<div className="bg-ink-950"><NotFound /></div>} />
    </Routes>
  );
}

export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  const [queryClient] = useState(() => client ?? createQueryClient());
  return (
    <QueryClientProvider client={queryClient}>
      <ToastProvider>
        <AuthProvider>{children}</AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Providers>
        <AppRoutes />
      </Providers>
    </BrowserRouter>
  );
}
