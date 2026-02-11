import type { ReactNode } from "react";
import { useTheme } from "./common/ThemeProvider";

type StatusCardProps = {
  label: string;
  value: string;
  icon?: ReactNode;
  tone?: "info" | "good" | "warning";
};

export default function StatusCard({
  label,
  value,
  icon,
  tone = "info",
}: StatusCardProps) {
  const { isDark } = useTheme();

  const cardToneClass = isDark
    ? "border-slate-700 bg-gradient-to-br from-slate-900/90 via-slate-900/85 to-cyan-950/20"
    : "border-slate-200 bg-gradient-to-br from-white/95 via-sky-50/55 to-emerald-50/40";

  const valueToneClass = isDark
    ? "border-slate-600 bg-slate-800/85 text-slate-100"
    : "border-slate-200 bg-white/95 text-slate-900";

  const iconToneClass = isDark
    ? "border-slate-600 bg-slate-800/85 text-cyan-200"
    : "border-slate-200 bg-white/95 text-sky-700";

  const toneDotClass = tone === "good"
    ? "bg-emerald-500"
    : tone === "warning"
      ? "bg-amber-500"
      : "bg-sky-500";
  const labelClass = isDark ? "text-slate-200" : "text-slate-700";

  return (
    <article
      className={`group relative overflow-hidden rounded-2xl border p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg ${cardToneClass}`}
    >
      <div className="pointer-events-none absolute -right-8 -top-10 h-20 w-20 rounded-full bg-white/20 blur-xl dark:bg-cyan-300/10" />
      <div className="flex items-start justify-between gap-3">
        <div className="inline-flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${toneDotClass}`} />
          <p className={`m-0 text-xs font-semibold uppercase tracking-[0.12em] ${labelClass}`}>
            {label}
          </p>
        </div>
        <span
          className={`inline-flex h-9 w-9 items-center justify-center rounded-lg border opacity-80 transition-transform duration-200 group-hover:scale-105 ${iconToneClass}`}
        >
          {icon}
        </span>
      </div>
      <div className="mt-3">
        <span
          className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold tracking-wide ${valueToneClass}`}
        >
          {value}
        </span>
      </div>
    </article>
  );
}
