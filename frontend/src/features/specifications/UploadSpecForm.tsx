import { useMutation, useQueryClient } from "@tanstack/react-query";
import { FileUp, UploadCloud, X } from "lucide-react";
import { useRef, useState, type DragEvent, type FormEvent } from "react";
import { ApiError } from "@/api/client";
import { specApi } from "@/api/endpoints";
import type { Specification } from "@/api/types";
import { Button } from "@/components/ui/Button";
import { Field, Input } from "@/components/ui/Field";
import { InlineError } from "@/components/ui/States";
import { cn } from "@/lib/cn";
import { formatBytes } from "@/lib/format";

const MAX_BYTES = 5 * 1024 * 1024;
const ACCEPTED = /\.(ya?ml|json)$/i;
const LABEL = /^[A-Za-z0-9][A-Za-z0-9._+-]{0,49}$/;

export function UploadSpecForm({ projectId, onUploaded }: { projectId: string; onUploaded: (spec: Specification) => void }) {
  const queryClient = useQueryClient();
  const input = useRef<HTMLInputElement>(null);
  const [file, setFile] = useState<File | null>(null);
  const [label, setLabel] = useState("");
  const [dragging, setDragging] = useState(false);
  const [errors, setErrors] = useState<{ file?: string; label?: string }>({});
  const upload = useMutation({
    mutationFn: ({ f, l }: { f: File; l: string }) => specApi.upload(projectId, f, l),
    onSuccess: (spec) => {
      void queryClient.invalidateQueries({ queryKey: ["specs", projectId] });
      void queryClient.invalidateQueries({ queryKey: ["dashboard"] });
      setFile(null);
      setLabel("");
      if (input.current) input.current.value = "";
      onUploaded(spec);
    },
  });

  const choose = (chosen: File | undefined) => {
    upload.reset();
    if (!chosen) return;
    if (!ACCEPTED.test(chosen.name)) { setErrors({ file: "Choose a .yaml, .yml or .json OpenAPI file." }); return; }
    if (chosen.size === 0) { setErrors({ file: "The file is empty." }); return; }
    if (chosen.size > MAX_BYTES) { setErrors({ file: `The file is ${formatBytes(chosen.size)}; the limit is 5 MB.` }); return; }
    setErrors({});
    setFile(chosen);
  };

  const onDrop = (event: DragEvent) => {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files[0]);
  };

  const submit = (event: FormEvent) => {
    event.preventDefault();
    const found: { file?: string; label?: string } = {};
    if (!file) found.file = "Choose a specification file.";
    if (!LABEL.test(label.trim())) found.label = "1–50 characters: letters, digits, '.', '_', '+' or '-' (e.g. v1.2.0).";
    setErrors(found);
    if (file && !found.label) upload.mutate({ f: file, l: label.trim() });
  };

  const apiError = upload.error instanceof ApiError ? upload.error : null;
  const issues = apiError && apiError.status === 422 ? apiError.errors : [];
  const labelError = errors.label ?? (apiError?.code === "VERSION_LABEL_TAKEN" ? apiError.message : undefined);

  return (
    <form onSubmit={submit} noValidate className="space-y-4">
      <div onDragOver={(e) => { e.preventDefault(); setDragging(true); }} onDragLeave={() => setDragging(false)} onDrop={onDrop}
        className={cn("relative flex flex-col items-center justify-center rounded-xl border border-dashed px-6 py-8 text-center transition-colors",
          dragging ? "border-accent-400 bg-accent-500/10" : errors.file ? "border-rose-500/60 bg-rose-500/5" : "border-ink-600 bg-ink-900/60 hover:border-ink-500")}>
        {file ? (
          <div className="flex w-full items-center gap-3 rounded-lg border border-ink-600 bg-ink-800 px-3 py-2.5 text-left">
            <FileUp className="size-5 shrink-0 text-accent-400" />
            <div className="min-w-0 flex-1">
              <p className="truncate text-sm text-ink-100">{file.name}</p>
              <p className="text-xs text-ink-400">{formatBytes(file.size)}</p>
            </div>
            <button type="button" aria-label="Remove file" className="rounded p-1 text-ink-300 hover:bg-ink-700"
              onClick={() => { setFile(null); upload.reset(); if (input.current) input.current.value = ""; }}>
              <X className="size-4" />
            </button>
          </div>
        ) : (
          <>
            <UploadCloud className="size-7 text-ink-300" />
            <p className="mt-3 text-sm text-ink-100">Drop an OpenAPI file here, or{" "}
              <button type="button" className="font-medium text-accent-300 hover:text-accent-200" onClick={() => input.current?.click()}>browse</button>
            </p>
            <p className="mt-1 text-xs text-ink-400">OpenAPI 3.x · YAML or JSON · up to 5 MB</p>
          </>
        )}
        <input ref={input} type="file" accept=".yaml,.yml,.json,application/json,application/yaml" className="sr-only"
          aria-label="Specification file" onChange={(e) => choose(e.target.files?.[0])} />
      </div>
      {errors.file ? <p className="-mt-2 text-xs text-rose-300">{errors.file}</p> : null}

      <Field label="Version label" error={labelError} hint="A unique name for this version, e.g. v1.4.0 or 2026-11-release.">
        {(props) => <Input {...props} placeholder="v1.0.0" value={label} onChange={(e) => setLabel(e.target.value)} />}
      </Field>

      {upload.isError && apiError?.code !== "VERSION_LABEL_TAKEN" ? (
        <div className="space-y-2">
          <InlineError error={upload.error} />
          {issues.length > 0 ? (
            <div className="rounded-lg border border-ink-700 bg-ink-950 p-3">
              <p className="mb-2 text-xs font-medium text-ink-200">Validation issues reported by the analyzer</p>
              <ul className="max-h-48 space-y-1.5 overflow-auto text-xs">
                {issues.map((issue, i) => (
                  <li key={i} className="flex gap-2">
                    {issue.pointer ? <code className="shrink-0 text-accent-300">{issue.pointer || "/"}</code> : null}
                    <span className="text-ink-200">{issue.message}</span>
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="flex justify-end">
        <Button type="submit" loading={upload.isPending} icon={<UploadCloud className="size-4" />}>Validate &amp; upload</Button>
      </div>
    </form>
  );
}
