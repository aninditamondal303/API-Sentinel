import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, Download, GitCompareArrows, ShieldCheck } from "lucide-react";
import { useState, type ReactNode } from "react";
import { Link, useNavigate, useParams } from "react-router";
import { ApiError, saveBlob } from "@/api/client";
import { projectApi, scanApi, specApi } from "@/api/endpoints";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { CopyButton } from "@/components/ui/CodeBlock";
import { PageHeader } from "@/components/ui/PageHeader";
import { ErrorState, InlineError, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { ContractTestsPanel } from "@/features/contracttests/ContractTestsPanel";
import { SecurityNotice } from "@/features/scans/SecurityNotice";
import { formatBytes, formatDateTime, pluralize } from "@/lib/format";

export function SpecDetailPage() {
  const { projectId = "", specId = "" } = useParams();
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [downloadError, setDownloadError] = useState<unknown>(null);
  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => projectApi.get(projectId) });
  const spec = useQuery({ queryKey: ["spec", projectId, specId], queryFn: () => specApi.get(projectId, specId) });
  const security = useMutation({
    mutationFn: () => scanApi.security(projectId, { specificationId: specId, useProjectPolicy: true }),
    onSuccess: (scan) => {
      void queryClient.invalidateQueries({ queryKey: ["scans", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Security scan complete: ${pluralize(scan.totalFindings, "finding")}.`);
      navigate(`/app/projects/${projectId}/scans/${scan.id}`);
    },
  });

  if (spec.isError) return <Card><ErrorState error={spec.error} onRetry={() => void spec.refetch()} /></Card>;
  if (!spec.data) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-56 rounded-xl" /></div>;
  const s = spec.data;
  const rows: [string, ReactNode][] = [
    ["API title", s.title],
    ["API version", s.apiVersion],
    ["OpenAPI", <Badge key="o">{s.openapiVersion}</Badge>],
    ["Format", s.format],
    ["Operations", s.operationCount],
    ["File", <span key="f" className="font-mono text-xs">{s.originalFilename}</span>],
    ["Size", formatBytes(s.sizeBytes)],
    ["Uploaded", formatDateTime(s.uploadedAt)],
  ];

  return (
    <>
      <PageHeader
        eyebrow={<Link to={`/app/projects/${projectId}`} className="inline-flex items-center gap-1 hover:text-ink-100"><ArrowLeft className="size-3.5" />{project.data?.name ?? "Project"}</Link>}
        title={<span className="font-mono">{s.versionLabel}</span>}
        description={`${s.title} · v${s.apiVersion}`}
        actions={
          <>
            <Button variant="secondary" icon={<Download className="size-4" />} onClick={() => {
              setDownloadError(null);
              specApi.content(projectId, specId, s.originalFilename).then(saveBlob).catch(setDownloadError);
            }}>Original file</Button>
            <ButtonLink variant="secondary" to={`/app/projects/${projectId}/compare?candidate=${specId}`} icon={<GitCompareArrows className="size-4" />}>Compare</ButtonLink>
            <Button icon={<ShieldCheck className="size-4" />} loading={security.isPending} onClick={() => security.mutate()}>
              {security.isPending ? "Scanning…" : "Run security scan"}
            </Button>
          </>
        } />

      <div className="space-y-6">
        <InlineError error={downloadError} />
        {security.isError ? (
          <div className="space-y-1">
            <InlineError error={security.error} />
            {security.error instanceof ApiError && security.error.scanId ? <p className="text-xs text-ink-300">The failed attempt was recorded in the scan history.</p> : null}
          </div>
        ) : null}
        <div className="grid gap-6 lg:grid-cols-[1.3fr_1fr]">
          <Card>
            <CardHeader title="Specification details" description="Metadata extracted by the analyzer during validation" />
            <dl className="grid gap-x-6 gap-y-4 p-5 sm:grid-cols-2">
              {rows.map(([label, value]) => (
                <div key={label}><dt className="text-xs text-ink-400">{label}</dt><dd className="mt-0.5 text-sm text-ink-100">{value}</dd></div>
              ))}
              <div className="sm:col-span-2">
                <dt className="text-xs text-ink-400">SHA-256</dt>
                <dd className="mt-0.5 flex items-center gap-2"><code className="truncate text-xs text-ink-200">{s.sha256}</code><CopyButton text={s.sha256} label="Copy SHA-256" /></dd>
              </div>
            </dl>
          </Card>
          <Card>
            <CardHeader title="Security hygiene" />
            <div className="space-y-4 p-5">
              <p className="text-sm text-ink-300">Review this version for security regressions and hygiene gaps using the project's threshold
                ({project.data?.policy.failOn ? `fail on ${project.data.policy.failOn.toLowerCase()}` : "threshold off"}).</p>
              <SecurityNotice />
            </div>
          </Card>
        </div>
        <ContractTestsPanel projectId={projectId} specId={specId} />
      </div>
    </>
  );
}
