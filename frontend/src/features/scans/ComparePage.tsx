import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, GitCompareArrows } from "lucide-react";
import { useState, type FormEvent } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { ApiError } from "@/api/client";
import { projectApi, scanApi, specApi } from "@/api/endpoints";
import { SEVERITIES, type Severity, type Specification } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Checkbox, Field, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { pluralize } from "@/lib/format";

function specOption(spec: Specification): string {
  return `${spec.versionLabel} · ${spec.title} v${spec.apiVersion} (${spec.operationCount} ops)`;
}

export function ComparePage() {
  const { projectId = "" } = useParams();
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => projectApi.get(projectId) });
  const specs = useQuery({ queryKey: ["specs", projectId], queryFn: () => specApi.list(projectId) });
  const items = specs.data?.items ?? [];
  // Newest first from the API: default baseline = second newest, candidate = newest.
  const [baseline, setBaseline] = useState(params.get("baseline") ?? "");
  const [candidate, setCandidate] = useState(params.get("candidate") ?? "");
  const [override, setOverride] = useState(false);
  const [failOn, setFailOn] = useState<Severity | "">("HIGH");
  const [manual, setManual] = useState(true);
  const [formError, setFormError] = useState<string | null>(null);
  const effectiveBaseline = baseline || items[1]?.id || "";
  const effectiveCandidate = candidate || items[0]?.id || "";

  const run = useMutation({
    mutationFn: () => scanApi.compatibility(projectId, {
      baselineSpecificationId: effectiveBaseline,
      candidateSpecificationId: effectiveCandidate,
      useProjectPolicy: !override,
      ...(override ? { failOn: failOn || null, failOnManualReview: manual } : {}),
    }),
    onSuccess: (scan) => {
      void queryClient.invalidateQueries({ queryKey: ["scans", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Scan complete: ${scan.decision === "PASS" ? "passed" : "failed"} with ${pluralize(scan.totalFindings, "finding")}.`);
      navigate(`/app/projects/${projectId}/scans/${scan.id}`);
    },
    onError: (error) => {
      if (error instanceof ApiError && error.scanId) {
        void queryClient.invalidateQueries({ queryKey: ["scans", projectId] });
      }
    },
  });

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (!effectiveBaseline || !effectiveCandidate) { setFormError("Choose a baseline and a candidate."); return; }
    if (effectiveBaseline === effectiveCandidate) { setFormError("Choose two different specifications."); return; }
    setFormError(null);
    run.mutate();
  };

  const header = (
    <PageHeader
      eyebrow={<Link to={`/app/projects/${projectId}`} className="inline-flex items-center gap-1 hover:text-ink-100"><ArrowLeft className="size-3.5" />{project.data?.name ?? "Project"}</Link>}
      title="Compatibility analysis"
      description="Compare a candidate version against a baseline to find changes that would break existing clients." />
  );

  if (specs.isError) return <>{header}<Card><ErrorState error={specs.error} onRetry={() => void specs.refetch()} /></Card></>;
  if (!specs.data || !project.data) return <>{header}<Skeleton className="h-80 rounded-xl" /></>;
  if (items.length < 2) {
    return (
      <>{header}
        <Card><EmptyState icon={<GitCompareArrows className="size-5" />} title="Two specifications are needed"
          description="Upload a baseline and a candidate version of the API to this project first."
          action={<Link to={`/app/projects/${projectId}`} className="text-sm font-medium text-accent-300">Go to the project</Link>} /></Card>
      </>
    );
  }

  const policy = project.data.policy;
  return (
    <>
      {header}
      <form onSubmit={submit} className="grid gap-6 xl:grid-cols-[1.5fr_1fr]">
        <Card>
          <CardHeader title="Versions" description="The baseline is what clients use today; the candidate is the proposed change." />
          <div className="grid items-end gap-4 p-5 lg:grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)]">
            <Field label="Baseline (current)">
              {(props) => (
                <Select {...props} value={effectiveBaseline} onChange={(e) => setBaseline(e.target.value)}>
                  {items.map((s) => <option key={s.id} value={s.id}>{specOption(s)}</option>)}
                </Select>
              )}
            </Field>
            <ArrowRight className="mx-auto mb-3 hidden size-5 text-ink-400 lg:block" aria-hidden="true" />
            <Field label="Candidate (proposed)">
              {(props) => (
                <Select {...props} value={effectiveCandidate} onChange={(e) => setCandidate(e.target.value)}>
                  {items.map((s) => <option key={s.id} value={s.id}>{specOption(s)}</option>)}
                </Select>
              )}
            </Field>
          </div>
        </Card>
        <Card>
          <CardHeader title="Release threshold" />
          <div className="space-y-4 p-5">
            <Checkbox label="Override the project policy for this scan" checked={override} onChange={setOverride}
              description={`Project policy: fail on ${policy.failOn ? policy.failOn.toLowerCase() : "nothing"}; manual review ${policy.failOnManualReview ? "blocks" : "does not block"}.`} />
            {override ? (
              <div className="space-y-4 rounded-lg border border-ink-700 bg-ink-950/60 p-4">
                <Field label="Fail when a finding is at least">
                  {(props) => (
                    <Select {...props} value={failOn} onChange={(e) => setFailOn(e.target.value as Severity | "")}>
                      {SEVERITIES.map((s) => <option key={s} value={s}>{s.charAt(0) + s.slice(1).toLowerCase()}</option>)}
                      <option value="">Never</option>
                    </Select>
                  )}
                </Field>
                <Checkbox label="Fail on findings that need manual review" checked={manual} onChange={setManual} />
              </div>
            ) : null}
          </div>
        </Card>
        <div className="space-y-3 xl:col-span-2">
          {formError ? <InlineError error={new Error(formError)} /> : null}
          <InlineError error={run.error} />
          {run.error instanceof ApiError && run.error.scanId ? (
            <p className="text-xs text-ink-300">The failed attempt was recorded in the <Link className="text-accent-300" to={`/app/projects/${projectId}?tab=scans`}>scan history</Link>.</p>
          ) : null}
          <div className="flex justify-end">
            <Button type="submit" size="lg" loading={run.isPending} icon={<GitCompareArrows className="size-4" />}>
              {run.isPending ? "Analyzing…" : "Run compatibility scan"}
            </Button>
          </div>
        </div>
      </form>
    </>
  );
}
