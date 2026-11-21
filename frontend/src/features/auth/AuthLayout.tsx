import type { ReactNode } from "react";
import { Logo } from "@/components/layout/Logo";

export function AuthLayout({ title, subtitle, children, footer }: {
  title: string;
  subtitle: string;
  children: ReactNode;
  footer: ReactNode;
}) {
  return (
    <div className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-ink-950 px-4 py-12">
      <div className="pointer-events-none absolute inset-0 grid-bg [mask-image:radial-gradient(ellipse_at_center,black_20%,transparent_70%)]" />
      <div className="pointer-events-none absolute top-[-10rem] h-[26rem] w-[40rem] rounded-full bg-accent-600/15 blur-[110px]" />
      <div className="relative w-full max-w-md animate-fade-in">
        <Logo className="mb-8 justify-center" />
        <div className="card p-7 sm:p-8">
          <h1 className="text-xl font-semibold tracking-tight text-ink-100">{title}</h1>
          <p className="mt-1 text-sm text-ink-300">{subtitle}</p>
          <div className="mt-6">{children}</div>
        </div>
        <div className="mt-6 text-center text-sm text-ink-300">{footer}</div>
      </div>
    </div>
  );
}
