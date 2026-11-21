import { CheckCircle2, AlertTriangle, X } from "lucide-react";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { cn } from "@/lib/cn";

type Tone = "success" | "error";
interface ToastItem { id: number; tone: Tone; message: string }
interface ToastApi { success: (message: string) => void; error: (message: string) => void }

const ToastContext = createContext<ToastApi | null>(null);
let nextId = 1;

export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<ToastItem[]>([]);
  const dismiss = useCallback((id: number) => setItems((all) => all.filter((t) => t.id !== id)), []);
  const push = useCallback((tone: Tone, message: string) => {
    const id = nextId++;
    setItems((all) => [...all.slice(-3), { id, tone, message }]);
    window.setTimeout(() => dismiss(id), tone === "error" ? 7000 : 4000);
  }, [dismiss]);
  const api = useMemo<ToastApi>(() => ({ success: (m) => push("success", m), error: (m) => push("error", m) }), [push]);
  return (
    <ToastContext.Provider value={api}>
      {children}
      <div className="pointer-events-none fixed bottom-4 right-4 z-50 flex w-80 flex-col gap-2" aria-live="polite">
        {items.map((toast) => (
          <div key={toast.id} role={toast.tone === "error" ? "alert" : "status"}
            className={cn("pointer-events-auto flex animate-fade-in items-start gap-2.5 rounded-xl border bg-ink-850/95 px-3.5 py-3 text-sm shadow-xl backdrop-blur",
              toast.tone === "success" ? "border-emerald-500/30" : "border-rose-500/40")}>
            {toast.tone === "success" ? <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-400" />
              : <AlertTriangle className="mt-0.5 size-4 shrink-0 text-rose-400" />}
            <p className="flex-1 text-ink-100">{toast.message}</p>
            <button type="button" onClick={() => dismiss(toast.id)} aria-label="Dismiss" className="text-ink-400 hover:text-ink-100">
              <X className="size-3.5" />
            </button>
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast(): ToastApi {
  const context = useContext(ToastContext);
  if (!context) throw new Error("useToast must be used inside ToastProvider");
  return context;
}
