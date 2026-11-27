import { useQuery } from "@tanstack/react-query";
import { BookOpen, Eye, ListFilter, Search } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { useLocation } from "react-router";
import { ruleApi } from "@/api/endpoints";
import type { Rule } from "@/api/types";
import { Badge, SeverityBadge, severityColor } from "@/components/ui/Badge";
import { Card } from "@/components/ui/Card";
import { Input, Select } from "@/components/ui/Field";
import { PageHeader } from "@/components/ui/PageHeader";
import { EmptyState, ErrorState, Skeleton } from "@/components/ui/States";
import { categoryLabel } from "@/lib/findings";
import { cn } from "@/lib/cn";

const CATEGORIES = ["COMPATIBILITY", "SECURITY_REGRESSION", "SPEC_HYGIENE"];

function matches(rule: Rule, needle: string): boolean {
  return [rule.id, rule.title, rule.impact, rule.remediation].some((v) => v.toLowerCase().includes(needle));
}

function RuleCard({ rule, highlighted }: { rule: Rule; highlighted: boolean }) {
  return (
    <article id={rule.id} className={cn("card scroll-mt-24 p-4", highlighted && "ring-2 ring-accent-500/60")}
      style={{ boxShadow: `inset 3px 0 0 0 ${severityColor[rule.severity]}` }}>
      <div className="flex flex-wrap items-center gap-2">
        <code className="text-xs font-semibold text-ink-200">{rule.id}</code>
        <SeverityBadge severity={rule.severity} />
        <Badge>{categoryLabel(rule.category)}</Badge>
        {rule.requiresManualReview ? <Badge tone="warning"><Eye className="size-3" />Manual review</Badge> : null}
      </div>
      <h2 className="mt-2 text-sm font-medium text-ink-100">{rule.title}</h2>
      <p className="mt-2 text-sm text-ink-300"><span className="font-medium text-ink-200">Impact: </span>{rule.impact}</p>
      <p className="mt-1 text-sm text-ink-300"><span className="font-medium text-ink-200">Fix: </span>{rule.remediation}</p>
    </article>
  );
}

/** Every rule the analyzer applies, from GET /api/v1/rules. Finding cards link here by rule id. */
export function RulesPage() {
  const rules = useQuery({ queryKey: ["rules"], queryFn: ruleApi.list, staleTime: Infinity });
  const [search, setSearch] = useState("");
  const [category, setCategory] = useState("");
  const { hash } = useLocation();
  const target = decodeURIComponent(hash.replace(/^#/, ""));

  const visible = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return (rules.data?.rules ?? []).filter((r) => (!category || r.category === category) && (!needle || matches(r, needle)));
  }, [rules.data, search, category]);

  useEffect(() => {
    if (target && rules.data) document.getElementById(target)?.scrollIntoView?.({ block: "start" });
  }, [target, rules.data]);

  return (
    <>
      <PageHeader eyebrow="Reference" title="Rules"
        description={rules.data
          ? `The ${rules.data.rules.length} deterministic rules behind every finding (ruleset ${rules.data.rulesetVersion}).`
          : "The deterministic rules behind every finding."} />
      {rules.isError ? <Card><ErrorState error={rules.error} onRetry={() => void rules.refetch()} /></Card> : (
        <>
          <div className="mb-4 flex flex-wrap items-center gap-3">
            <div className="relative min-w-56 flex-1">
              <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-ink-400" />
              <Input aria-label="Search rules" placeholder="Search by rule id or text" value={search} onChange={(e) => setSearch(e.target.value)}
                className="w-full rounded-lg border border-ink-600 bg-ink-900 pl-9 pr-3 text-sm focus:border-accent-500 focus:outline-none" />
            </div>
            <div className="flex items-center gap-2">
              <ListFilter className="size-4 text-ink-400" />
              <Select aria-label="Filter by category" value={category} onChange={(e) => setCategory(e.target.value)}
                className="w-48 rounded-lg border border-ink-600 bg-ink-900 px-3 text-sm">
                <option value="">All categories</option>
                {CATEGORIES.map((c) => <option key={c} value={c}>{categoryLabel(c)}</option>)}
              </Select>
            </div>
          </div>
          {!rules.data ? (
            <div className="space-y-3">{Array.from({ length: 4 }, (_, i) => <Skeleton key={i} className="h-28 rounded-xl" />)}</div>
          ) : visible.length === 0 ? (
            <Card><EmptyState icon={<BookOpen className="size-5" />} title="No matching rules" description="Try another search or category." /></Card>
          ) : (
            <div className="space-y-3">
              {visible.map((rule) => <RuleCard key={rule.id} rule={rule} highlighted={rule.id === target} />)}
            </div>
          )}
        </>
      )}
    </>
  );
}
