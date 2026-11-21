import { ArrowRight, FileCode2, GitCompareArrows, ShieldCheck, Upload, Workflow } from "lucide-react";
import { Link } from "react-router";
import { useAuth } from "@/auth/AuthContext";
import { Logo } from "@/components/layout/Logo";
import { ButtonLink } from "@/components/ui/Button";

const capabilities = [
  {
    icon: GitCompareArrows,
    title: "Compatibility checking",
    body: "Compare a baseline and a candidate OpenAPI spec. Removed endpoints, new required inputs, narrowed types and changed responses are classified by severity, with impact and remediation for each.",
  },
  {
    icon: ShieldCheck,
    title: "Security hygiene",
    body: "Review a specification for security regressions and hygiene gaps: missing authentication, weakened schemes and risky definitions, before the contract ships.",
  },
  {
    icon: FileCode2,
    title: "Contract-test generation",
    body: "Generate a ready-to-run pytest suite from the spec. Preview covered and skipped operations, then download the files and run them against your own environment.",
  },
];

const steps = [
  { icon: Upload, title: "Upload specs", body: "Add OpenAPI 3 JSON or YAML versions to a project. Each upload is validated before it is stored." },
  { icon: GitCompareArrows, title: "Run a scan", body: "Compare any two versions, or scan one for security hygiene, against your project's severity threshold." },
  { icon: Workflow, title: "Gate the release", body: "A clear pass or fail decision with reasons, every finding persisted for history and review." },
];

function DiffPreview() {
  return (
    <div className="card relative overflow-hidden" aria-label="Example of a compatibility finding">
      <div className="flex min-w-0 items-center gap-2 border-b border-ink-700/60 px-4 py-3">
        <span className="size-2.5 shrink-0 rounded-full bg-ink-600" /><span className="size-2.5 shrink-0 rounded-full bg-ink-600" /><span className="size-2.5 shrink-0 rounded-full bg-ink-600" />
        <span className="ml-2 truncate font-mono text-[11px] text-ink-400">orders-api · v1.0.0 → v2.0.0 · illustrative example</span>
      </div>
      <div className="space-y-3 p-4 font-mono text-[12px] leading-relaxed">
        <div className="rounded-lg border border-rose-500/30 bg-rose-500/[0.06] p-3">
          <div className="flex items-center gap-2 text-[11px]">
            <span className="rounded border border-sev-critical/50 bg-sev-critical/15 px-1.5 font-semibold uppercase text-rose-200">critical</span>
            <span className="text-rose-300">DELETE</span><span className="text-ink-200">/orders/{"{orderId}"}</span>
          </div>
          <p className="mt-2 font-sans text-[13px] text-ink-100">Operation removed</p>
          <p className="mt-1 font-sans text-xs text-ink-300">Clients calling this endpoint will receive 404 after the release.</p>
        </div>
        <div className="rounded-lg border border-orange-500/30 bg-orange-500/[0.05] p-3">
          <div className="flex items-center gap-2 text-[11px]">
            <span className="rounded border border-sev-high/50 bg-sev-high/15 px-1.5 font-semibold uppercase text-orange-200">high</span>
            <span className="text-emerald-300">POST</span><span className="text-ink-200">/orders</span>
          </div>
          <p className="mt-2 font-sans text-[13px] text-ink-100">New required request property</p>
          <div className="mt-2 grid grid-cols-1 gap-2 text-[11px] sm:grid-cols-2">
            <div className="break-words rounded bg-ink-950 px-2 py-1 text-rose-300">- required: [items]</div>
            <div className="break-words rounded bg-ink-950 px-2 py-1 text-emerald-300">+ required: [items, channel]</div>
          </div>
        </div>
        <div className="flex items-center justify-between gap-3 rounded-lg border border-ink-700 bg-ink-950 px-3 py-2 font-sans text-xs">
          <span className="text-ink-300">Decision with fail-on: HIGH</span>
          <span className="rounded-md border border-rose-500/40 bg-rose-500/10 px-2 py-0.5 font-medium text-rose-300">Fail</span>
        </div>
      </div>
    </div>
  );
}

export function LandingPage() {
  const { status } = useAuth();
  const signedIn = status === "authenticated";
  return (
    <div className="relative min-h-screen overflow-x-hidden bg-ink-950">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-[42rem] grid-bg [mask-image:radial-gradient(ellipse_at_top,black_30%,transparent_70%)]" />
      <div className="pointer-events-none absolute left-1/2 top-[-12rem] h-[32rem] w-[60rem] -translate-x-1/2 rounded-full bg-accent-600/20 blur-[120px]" />

      <header className="relative z-10 mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
        <Logo />
        <nav className="flex items-center gap-2">
          {signedIn ? <ButtonLink to="/app" size="sm">Open dashboard</ButtonLink> : (
            <>
              <Link to="/login" className="rounded-lg px-3 py-1.5 text-sm text-ink-200 hover:text-ink-100">Sign in</Link>
              <ButtonLink to="/register" size="sm">Get started</ButtonLink>
            </>
          )}
        </nav>
      </header>

      <main className="relative z-10">
        <section className="mx-auto grid max-w-6xl grid-cols-[minmax(0,1fr)] items-center gap-12 px-6 pb-20 pt-14 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:pt-24">
          <div className="animate-fade-in">
            <span className="inline-flex items-center gap-2 rounded-full border border-accent-500/30 bg-accent-500/10 px-3 py-1 text-xs font-medium text-accent-300">
              <span className="size-1.5 rounded-full bg-accent-400" /> OpenAPI governance for engineering teams
            </span>
            <h1 className="mt-5 text-4xl font-semibold leading-[1.08] tracking-tight text-ink-100 sm:text-5xl lg:text-[3.4rem]">
              Catch breaking changes <span className="bg-gradient-to-r from-accent-300 to-accent-500 bg-clip-text text-transparent">before they break production.</span>
            </h1>
            <p className="mt-5 max-w-xl text-base leading-relaxed text-ink-300 sm:text-lg">
              API Sentinel compares every version of your OpenAPI contract, flags what would break existing clients,
              reviews the spec for security hygiene and generates contract tests, so API changes ship with confidence.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <ButtonLink to={signedIn ? "/app" : "/register"} size="lg" icon={<ArrowRight className="size-4" />}>
                {signedIn ? "Go to dashboard" : "Create free account"}
              </ButtonLink>
              {!signedIn ? <ButtonLink to="/login" size="lg" variant="secondary">Sign in</ButtonLink> : null}
            </div>
            <p className="mt-6 text-xs text-ink-400">Supports OpenAPI 3.0 and 3.1 · JSON and YAML</p>
          </div>
          <div className="animate-fade-in [animation-delay:120ms]"><DiffPreview /></div>
        </section>

        <section className="border-y border-ink-800 bg-ink-900/40">
          <div className="mx-auto max-w-6xl px-6 py-20">
            <h2 className="text-2xl font-semibold tracking-tight text-ink-100 sm:text-3xl">One workflow for every API change</h2>
            <p className="mt-2 max-w-2xl text-ink-300">Three focused analyses built on a single rules engine, with every result stored for review and audit.</p>
            <div className="mt-10 grid gap-5 md:grid-cols-3">
              {capabilities.map(({ icon: Icon, title, body }) => (
                <div key={title} className="card group p-6 transition-colors hover:border-accent-500/40">
                  <div className="grid size-10 place-items-center rounded-lg border border-accent-500/30 bg-accent-500/10 text-accent-300 transition-transform group-hover:scale-105">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-5 font-semibold text-ink-100">{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-ink-300">{body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="mx-auto max-w-6xl px-6 py-20">
          <h2 className="text-2xl font-semibold tracking-tight text-ink-100 sm:text-3xl">How it works</h2>
          <ol className="mt-10 grid gap-5 md:grid-cols-3">
            {steps.map(({ icon: Icon, title, body }, index) => (
              <li key={title} className="relative rounded-xl border border-ink-700/60 p-6">
                <span className="font-mono text-xs text-accent-400">0{index + 1}</span>
                <Icon className="mt-3 size-5 text-ink-200" />
                <h3 className="mt-3 font-semibold text-ink-100">{title}</h3>
                <p className="mt-1.5 text-sm text-ink-300">{body}</p>
              </li>
            ))}
          </ol>
          <p className="mt-8 rounded-xl border border-ink-700/60 bg-ink-900/60 px-5 py-4 text-sm text-ink-300">
            <ShieldCheck className="mr-2 inline size-4 text-accent-400" />
            Security analysis in API Sentinel is <strong className="text-ink-100">specification-level</strong>: it reviews what your
            OpenAPI document declares. It does not send traffic to your API and is not a penetration test.
          </p>
        </section>

        <section className="mx-auto max-w-6xl px-6 pb-24">
          <div className="card flex flex-col items-start justify-between gap-6 bg-gradient-to-br from-ink-850 to-ink-900 p-8 sm:flex-row sm:items-center">
            <div>
              <h2 className="text-xl font-semibold text-ink-100">Put your next API release through API Sentinel</h2>
              <p className="mt-1 text-sm text-ink-300">Create a project, upload two versions and see what would break.</p>
            </div>
            <ButtonLink to={signedIn ? "/app" : "/register"} size="lg" icon={<ArrowRight className="size-4" />}>
              {signedIn ? "Open dashboard" : "Get started"}
            </ButtonLink>
          </div>
        </section>
      </main>

      <footer className="border-t border-ink-800 py-8 text-center text-xs text-ink-400">
        API Sentinel · Catch Breaking Changes Before They Break Production.
      </footer>
    </div>
  );
}
