import { X } from "lucide-react";
import { useEffect, useId, useRef, type ReactNode } from "react";

/** Modal built on the native <dialog> element (focus trapping and Esc handled by the browser). */
export function Dialog({ open, onClose, title, description, children }: {
  open: boolean;
  onClose: () => void;
  title: string;
  description?: string;
  children: ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const titleId = useId();
  useEffect(() => {
    const dialog = ref.current;
    if (!dialog) return;
    if (open && !dialog.open) {
      if (typeof dialog.showModal === "function") dialog.showModal();
      else dialog.setAttribute("open", "");
    } else if (!open && dialog.open) {
      if (typeof dialog.close === "function") dialog.close();
      else dialog.removeAttribute("open");
    }
  }, [open]);
  return (
    <dialog ref={ref} aria-labelledby={titleId} onCancel={(event) => { event.preventDefault(); onClose(); }}
      onClick={(event) => { if (event.target === ref.current) onClose(); }}
      className="m-auto w-[min(32rem,calc(100vw-2rem))] rounded-2xl border border-ink-600 bg-ink-850 p-0 text-ink-100 shadow-2xl backdrop:bg-ink-950/70 backdrop:backdrop-blur-sm">
      {open ? (
        <div className="p-6">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h2 id={titleId} className="text-base font-semibold">{title}</h2>
              {description ? <p className="mt-1 text-sm text-ink-300">{description}</p> : null}
            </div>
            <button type="button" onClick={onClose} className="rounded-md p-1 text-ink-300 hover:bg-ink-700 hover:text-ink-100" aria-label="Close">
              <X className="size-4" />
            </button>
          </div>
          {children}
        </div>
      ) : null}
    </dialog>
  );
}
