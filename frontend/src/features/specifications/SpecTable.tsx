import { ChevronRight, FileCode2 } from "lucide-react";
import { Link } from "react-router";
import type { Specification } from "@/api/types";
import { Badge } from "@/components/ui/Badge";
import { formatBytes, formatRelative } from "@/lib/format";

export function SpecTable({ projectId, specs }: { projectId: string; specs: Specification[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-ink-700/60 text-xs text-ink-400">
            <th scope="col" className="px-5 py-2.5 font-medium">Version</th>
            <th scope="col" className="px-3 py-2.5 font-medium">API</th>
            <th scope="col" className="px-3 py-2.5 font-medium">OpenAPI</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Operations</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Size</th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium">Uploaded</th>
          </tr>
        </thead>
        <tbody>
          {specs.map((spec) => (
            <tr key={spec.id} className="group border-b border-ink-800 last:border-0 hover:bg-ink-800/40">
              <td className="px-5 py-3">
                <Link to={`/app/projects/${projectId}/specifications/${spec.id}`} className="inline-flex items-center gap-2 font-mono text-[13px] text-ink-100 hover:text-accent-300">
                  <FileCode2 className="size-4 text-accent-400" />{spec.versionLabel}
                  <ChevronRight className="size-3.5 text-ink-500 opacity-0 group-hover:opacity-100" />
                </Link>
                <p className="mt-0.5 truncate pl-6 text-xs text-ink-400">{spec.originalFilename}</p>
              </td>
              <td className="max-w-56 px-3 py-3"><p className="truncate text-ink-100">{spec.title}</p><p className="text-xs text-ink-400">v{spec.apiVersion}</p></td>
              <td className="whitespace-nowrap px-3 py-3"><Badge>{spec.openapiVersion}</Badge> <Badge>{spec.format}</Badge></td>
              <td className="px-3 py-3 text-right tabular-nums text-ink-200">{spec.operationCount}</td>
              <td className="whitespace-nowrap px-3 py-3 text-right tabular-nums text-ink-300">{formatBytes(spec.sizeBytes)}</td>
              <td className="whitespace-nowrap px-5 py-3 text-right text-xs text-ink-300" title={spec.uploadedAt}>{formatRelative(spec.uploadedAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
