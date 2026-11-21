import { useId } from "react";
import { Link } from "react-router";
import { cn } from "@/lib/cn";

export function LogoMark({ className }: { className?: string }) {
  const gradient = `logo-gradient-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 32 32" className={cn("size-7", className)} aria-hidden="true">
      <defs>
        <linearGradient id={gradient} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#60a5fa" />
          <stop offset="1" stopColor="#2563eb" />
        </linearGradient>
      </defs>
      <rect width="32" height="32" rx="8" fill="#0d1423" stroke="#22304c" />
      <path d="M16 5.5l8.5 3.3v6.4c0 5.3-3.5 9.3-8.5 11.1-5-1.8-8.5-5.8-8.5-11.1V8.8z" fill="none" stroke={`url(#${gradient})`} strokeWidth="2" strokeLinejoin="round" />
      <path d="M11.8 16.1l3 3 5.5-5.9" fill="none" stroke="#93c5fd" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
}

export function Logo({ to = "/", className }: { to?: string; className?: string }) {
  return (
    <Link to={to} className={cn("flex items-center gap-2.5 font-semibold tracking-tight text-ink-100", className)}>
      <LogoMark />
      <span>API Sentinel</span>
    </Link>
  );
}
