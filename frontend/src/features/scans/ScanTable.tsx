import { ArrowUpRight, GitCompareArrows, ShieldCheck } from "lucide-react";
import { Link } from "react-router";
import type { Scan } from "@/api/types";
import { DecisionBadge } from "@/components/ui/Badge";
import { formatRelative } from "@/lib/format";

export function scanPath(scan: Scan): string {
  return `/app/projects/${scan.projectId}/scans/${scan.id}`;
}

export function ScanTypeLabel({ scan }: { scan: Scan }) {
  return scan.type === "COMPATIBILITY" ? (
    <span className="inline-flex items-center gap-1.5 text-ink-200"><GitCompareArrows className="size-3.5 text-accent-400" />Compatibility</span>
  ) : (
    <span className="inline-flex items-center gap-1.5 text-ink-200"><ShieldCheck className="size-3.5 text-violet-300" />Security</span>
  );
}

export function SpecsLabel({ scan }: { scan: Scan }) {
  return scan.baseline ? (
    <span className="font-mono text-xs text-ink-200">{scan.baseline.versionLabel} <span className="text-ink-400">→</span> {scan.target.versionLabel}</span>
  ) : (
    <span className="font-mono text-xs text-ink-200">{scan.target.versionLabel}</span>
  );
}

export function ScanTable({ scans, projectNames }: { scans: Scan[]; projectNames?: Map<string, string> }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[640px] text-left text-sm">
        <thead>
          <tr className="border-b border-ink-700/60 text-xs text-ink-400">
            <th scope="col" className="px-5 py-2.5 font-medium">Type</th>
            {projectNames ? <th scope="col" className="px-3 py-2.5 font-medium">Project</th> : null}
            <th scope="col" className="px-3 py-2.5 font-medium">Specifications</th>
            <th scope="col" className="px-3 py-2.5 font-medium">Result</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Findings</th>
            <th scope="col" className="px-3 py-2.5 text-right font-medium">Breaking</th>
            <th scope="col" className="px-5 py-2.5 text-right font-medium">When</th>
          </tr>
        </thead>
        <tbody>
          {scans.map((scan) => (
            <tr key={scan.id} className="group border-b border-ink-800 last:border-0 hover:bg-ink-800/40">
              <td className="px-5 py-3">
                <Link to={scanPath(scan)} className="inline-flex items-center gap-1 rounded hover:underline" aria-label={`Open ${scan.type.toLowerCase()} scan`}>
                  <ScanTypeLabel scan={scan} />
                  <ArrowUpRight className="size-3.5 text-ink-500 opacity-0 transition-opacity group-hover:opacity-100" />
                </Link>
              </td>
              {projectNames ? <td className="max-w-48 truncate px-3 py-3 text-ink-200">{projectNames.get(scan.projectId) ?? "—"}</td> : null}
              <td className="px-3 py-3"><SpecsLabel scan={scan} /></td>
              <td className="px-3 py-3"><DecisionBadge decision={scan.decision} status={scan.status} /></td>
              <td className="px-3 py-3 text-right tabular-nums text-ink-200">{scan.status === "COMPLETED" ? scan.totalFindings : "—"}</td>
              <td className="px-3 py-3 text-right tabular-nums">
                {scan.type === "COMPATIBILITY" && scan.status === "COMPLETED"
                  ? <span className={scan.breakingChanges > 0 ? "text-rose-300" : "text-ink-300"}>{scan.breakingChanges}</span>
                  : <span className="text-ink-500">—</span>}
              </td>
              <td className="whitespace-nowrap px-5 py-3 text-right text-xs text-ink-300" title={scan.createdAt}>{formatRelative(scan.createdAt)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
