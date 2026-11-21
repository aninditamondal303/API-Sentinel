import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, FileCode2, FlaskConical, Play } from "lucide-react";
import { useState, type FormEvent } from "react";
import { saveBlob } from "@/api/client";
import { contractTestApi, type ContractTestOptions } from "@/api/endpoints";
import { Badge, MethodBadge } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card, CardHeader } from "@/components/ui/Card";
import { CodeBlock, CopyButton } from "@/components/ui/CodeBlock";
import { Checkbox, Field, Input } from "@/components/ui/Field";
import { EmptyState, ErrorState, InlineError, Skeleton } from "@/components/ui/States";
import { Tabs } from "@/components/ui/Tabs";
import { useToast } from "@/components/ui/Toast";

function validBaseUrl(value: string): boolean {
  if (!value) return true;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}

export function ContractTestsPanel({ projectId, specId }: { projectId: string; specId: string }) {
  const toast = useToast();
  const [baseUrl, setBaseUrl] = useState("");
  const [unsafe, setUnsafe] = useState(false);
  const [options, setOptions] = useState<ContractTestOptions | null>(null);
  const [baseUrlError, setBaseUrlError] = useState<string>();
  const [file, setFile] = useState<string>("");

  const preview = useQuery({
    queryKey: ["contract-tests", projectId, specId, options],
    queryFn: () => contractTestApi.preview(projectId, specId, options!),
    enabled: options !== null,
    retry: false,
  });
  const zip = useMutation({
    mutationFn: () => contractTestApi.download(projectId, specId, options!),
    onSuccess: (result) => { saveBlob(result); toast.success(`Downloaded ${result.filename}.`); },
  });

  const generate = (event: FormEvent) => {
    event.preventDefault();
    const trimmed = baseUrl.trim();
    if (!validBaseUrl(trimmed)) { setBaseUrlError("Use an http:// or https:// URL."); return; }
    setBaseUrlError(undefined);
    setFile("");
    setOptions({ includeUnsafeMethods: unsafe, ...(trimmed ? { baseUrl: trimmed } : {}) });
  };

  const data = preview.data;
  const activeFile = data?.files.find((f) => f.path === file) ?? data?.files[0];

  return (
    <Card>
      <CardHeader title={<span className="inline-flex items-center gap-2"><FlaskConical className="size-4 text-accent-400" />Contract tests</span>}
        description="Generate a pytest suite from this specification. Tests are not executed by API Sentinel; run them against your own environment." />
      <form onSubmit={generate} noValidate className="grid items-start gap-4 border-b border-ink-700/60 p-5 xl:grid-cols-[1fr_auto]">
        <div className="grid gap-4 lg:grid-cols-2">
          <Field label="Default base URL (optional)" error={baseUrlError} hint="Written into the suite; can be overridden with APISENTINEL_BASE_URL.">
            {(props) => <Input {...props} placeholder="https://staging.example.com" value={baseUrl} onChange={(e) => setBaseUrl(e.target.value)} />}
          </Field>
          <div className="lg:pt-6">
            <Checkbox label="Include unsafe methods" checked={unsafe} onChange={setUnsafe}
              description="Also generate tests for POST, PUT, PATCH and DELETE operations." />
          </div>
        </div>
        <Button type="submit" className="justify-self-start xl:mt-6" icon={<Play className="size-4" />} loading={preview.isFetching}>Generate preview</Button>
      </form>

      {options === null ? (
        <EmptyState icon={<FlaskConical className="size-5" />} title="No suite generated yet"
          description="Choose the options above and generate a preview. You can then download the exact files as a ZIP." />
      ) : preview.isError ? (
        <ErrorState error={preview.error} onRetry={() => void preview.refetch()} />
      ) : !data ? (
        <div className="space-y-3 p-5"><Skeleton className="h-16" /><Skeleton className="h-48" /></div>
      ) : (
        <div className="space-y-6 p-5">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <dl className="flex flex-wrap gap-6 text-sm">
              {[["Operations", data.summary.total], ["Ready", data.summary.ready], ["Skipped", data.summary.skipped], ["Schema-validated", data.summary.schemaValidated]].map(([label, value]) => (
                <div key={label as string}><dt className="text-xs text-ink-400">{label}</dt><dd className="text-xl font-semibold tabular-nums">{value}</dd></div>
              ))}
            </dl>
            <Button icon={<Download className="size-4" />} loading={zip.isPending} onClick={() => zip.mutate()}>Download ZIP</Button>
          </div>
          <InlineError error={zip.error} />

          <div className="overflow-x-auto rounded-lg border border-ink-700">
            <table className="w-full min-w-[560px] text-left text-sm">
              <thead><tr className="border-b border-ink-700 bg-ink-900 text-xs text-ink-400">
                <th scope="col" className="px-4 py-2 font-medium">Operation</th>
                <th scope="col" className="px-3 py-2 font-medium">Status</th>
                <th scope="col" className="px-4 py-2 font-medium">Expected / reason</th>
              </tr></thead>
              <tbody>
                {data.operations.map((op) => (
                  <tr key={op.id} className="border-b border-ink-800 last:border-0">
                    <td className="px-4 py-2.5"><MethodBadge method={op.method} /> <span className="font-mono text-xs text-ink-100">{op.path}</span>
                      {op.requiresAuth ? <Badge className="ml-2">auth</Badge> : null}</td>
                    <td className="px-3 py-2.5">{op.status === "ready" ? <Badge tone="success">Ready</Badge> : <Badge tone="warning">Skipped</Badge>}</td>
                    <td className="px-4 py-2.5 text-xs text-ink-300">{op.status === "ready" ? (op.expectedStatuses ?? []).join(", ") : op.skipReason}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {data.files.length > 0 && activeFile ? (
            <div>
              <Tabs label="Generated files" value={activeFile.path} onChange={setFile} className="mb-3"
                items={data.files.map((f) => ({ key: f.path, label: <><FileCode2 className="size-3.5" />{f.path}</> }))} />
              <div className="mb-2 flex justify-end"><CopyButton text={activeFile.content} label={`Copy ${activeFile.path}`} /></div>
              <CodeBlock code={activeFile.content} />
            </div>
          ) : null}

          <div>
            <p className="mb-1.5 text-xs font-medium text-ink-300">Run the suite</p>
            <div className="flex items-center gap-2 rounded-lg border border-ink-700 bg-ink-950 px-3 py-2">
              <code className="flex-1 overflow-x-auto whitespace-nowrap text-xs text-accent-200">{data.runCommand}</code>
              <CopyButton text={data.runCommand} label="Copy run command" />
            </div>
          </div>
        </div>
      )}
    </Card>
  );
}
