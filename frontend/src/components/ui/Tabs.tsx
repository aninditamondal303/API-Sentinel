import { useRef, type KeyboardEvent, type ReactNode } from "react";
import { cn } from "@/lib/cn";

export interface TabItem<K extends string> {
  key: K;
  label: ReactNode;
  count?: number;
}

/** Accessible tablist (arrow-key navigation); the caller renders the active panel. */
export function Tabs<K extends string>({ items, value, onChange, label, className }: {
  items: TabItem<K>[];
  value: K;
  onChange: (key: K) => void;
  label: string;
  className?: string;
}) {
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const onKeyDown = (event: KeyboardEvent, index: number) => {
    if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
    event.preventDefault();
    const next = (index + (event.key === "ArrowRight" ? 1 : -1) + items.length) % items.length;
    refs.current[next]?.focus();
    onChange(items[next]!.key);
  };
  return (
    <div role="tablist" aria-label={label} className={cn("flex gap-1 overflow-x-auto overflow-y-hidden border-b border-ink-700/70 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden", className)}>
      {items.map((item, index) => {
        const active = item.key === value;
        return (
          <button key={item.key} ref={(el) => { refs.current[index] = el; }} role="tab" type="button"
            aria-selected={active} tabIndex={active ? 0 : -1} onClick={() => onChange(item.key)}
            onKeyDown={(event) => onKeyDown(event, index)}
            className={cn("relative -mb-px flex items-center gap-2 whitespace-nowrap border-b-2 px-3 py-2.5 text-sm transition-colors",
              active ? "border-accent-400 text-ink-100" : "border-transparent text-ink-300 hover:text-ink-100")}>
            {item.label}
            {item.count !== undefined ? (
              <span className={cn("rounded-full px-1.5 text-[11px] tabular-nums", active ? "bg-accent-500/20 text-accent-300" : "bg-ink-700 text-ink-300")}>
                {item.count}
              </span>
            ) : null}
          </button>
        );
      })}
    </div>
  );
}
