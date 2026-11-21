import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, FileCode2, GitCompareArrows, History, Settings2, Trash2, UploadCloud } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router";
import { projectApi, scanApi, specApi } from "@/api/endpoints";
import type { ScanStatus, ScanType } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { Button, ButtonLink } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";
import { ScanTable } from "@/features/scans/ScanTable";
import { SpecTable } from "@/features/specifications/SpecTable";
import { UploadSpecForm } from "@/features/specifications/UploadSpecForm";
import { formatDateTime } from "@/lib/format";
import { PolicyEditor } from "./PolicyEditor";
import { ProjectForm } from "./ProjectForm";

type Tab = "specifications" | "scans" | "settings";

function ScanHistory({ projectId }: { projectId: string }) {
  const [type, setType] = useState<ScanType | "">("");
  const [status, setStatus] = useState<ScanStatus | "">("");
  const [page, setPage] = useState(0);
  const scans = useQuery({
    queryKey: ["scans", projectId, type, status, page],
    queryFn: () => scanApi.list(projectId, { ...(type ? { type } : {}), ...(status ? { status } : {}), page, size: 20 }),
    placeholderData: (previous) => previous,
  });
  return (
    <Card>
      <CardHeader title="Scan history" description="Every scan is stored with its findings and the threshold it used."
        action={
          <div className="flex gap-2">
            <Select aria-label="Filter by type" className="h-8 w-40 rounded-lg border border-ink-600 bg-ink-900 px-2 text-xs"
              value={type} onChange={(e) => { setType(e.target.value as ScanType | ""); setPage(0); }}>
              <option value="">All types</option><option value="COMPATIBILITY">Compatibility</option><option value="SECURITY">Security</option>
            </Select>
            <Select aria-label="Filter by status" className="h-8 w-36 rounded-lg border border-ink-600 bg-ink-900 px-2 text-xs"
              value={status} onChange={(e) => { setStatus(e.target.value as ScanStatus | ""); setPage(0); }}>
              <option value="">All statuses</option><option value="COMPLETED">Completed</option><option value="FAILED">Errored</option><option value="RUNNING">Running</option>
            </Select>
          </div>
        } />
      {scans.isError ? <ErrorState error={scans.error} onRetry={() => void scans.refetch()} />
        : !scans.data ? <div className="space-y-2 p-5">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-9" />)}</div>
        : scans.data.items.length === 0 ? <EmptyState icon={<History className="size-5" />} title="No scans match"
            description={type || status ? "Try clearing the filters." : "Run a compatibility scan or a security scan to start the history."} />
        : (
          <>
            <ScanTable scans={scans.data.items} />
            {scans.data.totalPages > 1 ? (
              <div className="flex items-center justify-between border-t border-ink-700/60 px-5 py-3 text-xs text-ink-300">
                <span>Page {scans.data.page + 1} of {scans.data.totalPages} · {scans.data.totalItems} scans</span>
                <div className="flex gap-2">
                  <Button size="sm" variant="secondary" disabled={page === 0} onClick={() => setPage((p) => p - 1)}>Previous</Button>
                  <Button size="sm" variant="secondary" disabled={page + 1 >= scans.data.totalPages} onClick={() => setPage((p) => p + 1)}>Next</Button>
                </div>
              </div>
            ) : null}
          </>
        )}
    </Card>
  );
}

export function ProjectDetailPage() {
  const { projectId = "" } = useParams();
  const [params, setParams] = useSearchParams();
  const tab = (["specifications", "scans", "settings"].includes(params.get("tab") ?? "") ? params.get("tab") : "specifications") as Tab;
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const [uploading, setUploading] = useState(false);
  const [editing, setEditing] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const project = useQuery({ queryKey: ["project", projectId], queryFn: () => projectApi.get(projectId) });
  const specs = useQuery({ queryKey: ["specs", projectId], queryFn: () => specApi.list(projectId) });
  const scanCount = useQuery({ queryKey: ["scans", projectId, "count"], queryFn: () => scanApi.list(projectId, { size: 1 }) });
  const remove = useMutation({
    mutationFn: () => projectApi.remove(projectId),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success("Project deleted.");
      navigate("/app/projects", { replace: true });
    },
  });

  if (project.isError) {
    return <Card><ErrorState error={project.error} onRetry={() => void project.refetch()} /></Card>;
  }
  if (!project.data) return <div className="space-y-4"><Skeleton className="h-12 w-72" /><Skeleton className="h-64 rounded-xl" /></div>;
  const p = project.data;
  const specCount = specs.data?.totalItems ?? 0;

  return (
    <>
      <PageHeader
        eyebrow={<Link to="/app/projects" className="inline-flex items-center gap-1 hover:text-ink-100"><ArrowLeft className="size-3.5" />Projects</Link>}
        title={p.name}
        description={p.description || undefined}
        actions={
          <>
            <Button variant="secondary" icon={<UploadCloud className="size-4" />} onClick={() => setUploading(true)}>Upload spec</Button>
            {specCount >= 2 ? (
              <ButtonLink to={`/app/projects/${projectId}/compare`} icon={<GitCompareArrows className="size-4" />}>Compare versions</ButtonLink>
            ) : (
              <Button disabled title="Upload at least two specifications to compare" icon={<GitCompareArrows className="size-4" />}>Compare versions</Button>
            )}
          </>
        } />

      <div className="mb-6 flex flex-wrap gap-2 text-xs">
        <Badge tone="accent">Fail on: {p.policy.failOn ? p.policy.failOn.toLowerCase() : "off"}</Badge>
        <Badge>Manual review {p.policy.failOnManualReview ? "blocks" : "does not block"}</Badge>
        <Badge>Created {formatDateTime(p.createdAt)}</Badge>
      </div>

      <Tabs label="Project sections" value={tab} onChange={(key) => setParams({ tab: key }, { replace: true })} className="mb-6"
        items={[
          { key: "specifications", label: <><FileCode2 className="size-4" />Specifications</>, ...(specs.data ? { count: specs.data.totalItems } : {}) },
          { key: "scans", label: <><History className="size-4" />Scans</>, ...(scanCount.data ? { count: scanCount.data.totalItems } : {}) },
          { key: "settings", label: <><Settings2 className="size-4" />Policy &amp; settings</> },
        ]} />

      {tab === "specifications" ? (
        <Card>
          <CardHeader title="Specifications" description="Uploaded OpenAPI versions. Each was validated by the analyzer before it was stored."
            action={<Button size="sm" variant="secondary" icon={<UploadCloud className="size-3.5" />} onClick={() => setUploading(true)}>Upload</Button>} />
          {specs.isError ? <ErrorState error={specs.error} onRetry={() => void specs.refetch()} />
            : !specs.data ? <div className="space-y-2 p-5">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-10" />)}</div>
            : specs.data.items.length === 0 ? (
              <EmptyState icon={<FileCode2 className="size-5" />} title="No specifications yet"
                description="Upload a baseline version of your OpenAPI document, then a candidate version to compare against it."
                action={<Button size="sm" icon={<UploadCloud className="size-4" />} onClick={() => setUploading(true)}>Upload baseline</Button>} />
            ) : <SpecTable projectId={projectId} specs={specs.data.items} />}
        </Card>
      ) : null}

      {tab === "scans" ? <ScanHistory projectId={projectId} /> : null}

      {tab === "settings" ? (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader title="Compatibility policy" description="The default threshold for compatibility and security scans in this project." />
            <div className="p-5"><PolicyEditor key={`${p.policy.failOn}-${p.policy.failOnManualReview}`} project={p} /></div>
          </Card>
          <Card>
            <CardHeader title="Project details" />
            <div className="space-y-4 p-5">
              <Button variant="secondary" onClick={() => setEditing(true)}>Rename or edit description</Button>
              <div className="rounded-lg border border-rose-500/20 bg-rose-500/[0.04] p-4">
                <p className="text-sm font-medium text-ink-100">Delete project</p>
                <p className="mt-1 text-xs text-ink-300">Permanently deletes its specifications, scans and findings.</p>
                <Button variant="danger" size="sm" className="mt-3" icon={<Trash2 className="size-3.5" />} onClick={() => setDeleting(true)}>Delete project</Button>
              </div>
            </div>
          </Card>
        </div>
      ) : null}

      <Dialog open={uploading} onClose={() => setUploading(false)} title="Upload specification"
        description="The file is validated by the analyzer. Invalid documents are rejected with the exact issues.">
        <UploadSpecForm projectId={projectId} onUploaded={(spec) => {
          setUploading(false);
          setParams({ tab: "specifications" }, { replace: true });
          toast.success(`Uploaded ${spec.versionLabel}: ${spec.operationCount} operations, OpenAPI ${spec.openapiVersion}.`);
        }} />
      </Dialog>

      <Dialog open={editing} onClose={() => setEditing(false)} title="Edit project">
        <ProjectForm initial={{ name: p.name, description: p.description ?? "" }} submitLabel="Save changes" onCancel={() => setEditing(false)}
          onSubmit={async (values) => {
            await projectApi.update(projectId, { name: values.name, description: values.description || null });
            void queryClient.invalidateQueries({ queryKey: ["project", projectId] });
            void queryClient.invalidateQueries({ queryKey: ["projects"] });
            setEditing(false);
            toast.success("Project updated.");
          }} />
      </Dialog>

      <Dialog open={deleting} onClose={() => setDeleting(false)} title={`Delete "${p.name}"?`}
        description="This removes the project with all of its specifications, scans and findings. It cannot be undone.">
        <InlineError error={remove.error} />
        <div className="mt-4 flex justify-end gap-2">
          <Button variant="ghost" onClick={() => setDeleting(false)}>Cancel</Button>
          <Button variant="danger" loading={remove.isPending} onClick={() => remove.mutate()}>Delete permanently</Button>
        </div>
      </Dialog>
    </>
  );
}
