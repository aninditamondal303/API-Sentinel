import { Info } from "lucide-react";

export function SecurityNotice() {
  return (
    <div className="flex gap-2.5 rounded-lg border border-violet-400/25 bg-violet-500/[0.07] px-3.5 py-3 text-xs leading-relaxed text-violet-100/90" role="note">
      <Info className="mt-0.5 size-4 shrink-0 text-violet-300" />
      <p>
        <strong className="font-semibold text-violet-100">Specification-level analysis.</strong> These checks read what the OpenAPI
        document declares (authentication, schemes, definitions). No requests are sent to your API, and this is not a penetration test.
      </p>
    </div>
  );
}
