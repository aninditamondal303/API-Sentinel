import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { ChevronRight, FolderKanban, Plus } from "lucide-react";
import { Link, useNavigate, useSearchParams } from "react-router";
import { projectApi } from "@/api/endpoints";
import { Badge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { Dialog } from "@/components/ui/Dialog";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { useToast } from "@/components/ui/Toast";
import { formatRelative } from "@/lib/format";
import { ProjectForm } from "./ProjectForm";

export function ProjectsPage() {
  const [params, setParams] = useSearchParams();
  const creating = params.get("new") === "1";
  const setCreating = (open: boolean) => setParams(open ? { new: "1" } : {}, { replace: true });
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();
  const projects = useQuery({ queryKey: ["projects"], queryFn: () => projectApi.list() });
  const create = useMutation({
    mutationFn: projectApi.create,
    onSuccess: (project) => {
      void queryClient.invalidateQueries({ queryKey: ["projects"] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      toast.success(`Project "${project.name}" created.`);
      navigate(`/app/projects/${project.id}`);
    },
  });

  return (
    <>
      <PageHeader eyebrow="Workspace" title="Projects" description="Each project holds the versions of one API, its compatibility policy and its scan history."
        actions={<Button icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>New project</Button>} />

      {projects.isError ? <Card><ErrorState error={projects.error} onRetry={() => void projects.refetch()} /></Card>
        : !projects.data ? (
          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">{Array.from({ length: 3 }, (_, i) => <Skeleton key={i} className="h-36 rounded-xl" />)}</div>
        ) : projects.data.items.length === 0 ? (
          <Card>
            <EmptyState icon={<FolderKanban className="size-5" />} title="No projects yet"
              description="Create a project for an API, then upload its OpenAPI versions to compare them."
              action={<Button size="sm" icon={<Plus className="size-4" />} onClick={() => setCreating(true)}>Create your first project</Button>} />
          </Card>
        ) : (
          <ul className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {projects.data.items.map((project) => (
              <li key={project.id}>
                <Link to={`/app/projects/${project.id}`} className="card group flex h-full flex-col p-5 transition-all hover:-translate-y-0.5 hover:border-accent-500/40">
                  <div className="flex items-start justify-between gap-3">
                    <div className="grid size-9 place-items-center rounded-lg border border-ink-600 bg-ink-800 text-accent-400"><FolderKanban className="size-4" /></div>
                    <ChevronRight className="size-4 text-ink-500 transition-transform group-hover:translate-x-0.5 group-hover:text-ink-200" />
                  </div>
                  <h2 className="mt-4 truncate font-semibold text-ink-100">{project.name}</h2>
                  <p className="mt-1 line-clamp-2 min-h-10 text-sm text-ink-300">{project.description || "No description"}</p>
                  <div className="mt-4 flex items-center justify-between text-xs text-ink-400">
                    <Badge tone="accent">Fail on {project.policy.failOn ? project.policy.failOn.toLowerCase() : "off"}</Badge>
                    <span>Updated {formatRelative(project.updatedAt)}</span>
                  </div>
                </Link>
              </li>
            ))}
          </ul>
        )}

      <Dialog open={creating} onClose={() => setCreating(false)} title="New project" description="Group the versions of one API under a project.">
        <ProjectForm submitLabel="Create project" onCancel={() => setCreating(false)}
          onSubmit={async (values) => { await create.mutateAsync({ name: values.name, ...(values.description ? { description: values.description } : {}) }); }} />
      </Dialog>
    </>
  );
}
