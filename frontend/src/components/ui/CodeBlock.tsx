import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { cn } from "@/lib/cn";

export function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <button type="button" aria-label={label}
      className="inline-flex items-center gap-1 rounded-md px-2 py-1 text-xs text-ink-300 hover:bg-ink-700 hover:text-ink-100"
      onClick={() => {
        void navigator.clipboard?.writeText(text).then(() => {
          setCopied(true);
          window.setTimeout(() => setCopied(false), 1500);
        });
      }}>
      {copied ? <Check className="size-3.5 text-emerald-400" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : "Copy"}
    </button>
  );
}

export function CodeBlock({ code, className, maxHeight = "28rem" }: { code: string; className?: string; maxHeight?: string }) {
  return (
    <pre className={cn("overflow-auto rounded-lg border border-ink-700 bg-ink-950 p-4 text-[12.5px] leading-relaxed text-ink-200", className)}
      style={{ maxHeight }}>
      <code>{code}</code>
    </pre>
  );
}
