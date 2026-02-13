import type { ReactNode } from "react";
import { useTheme } from "./common/ThemeProvider";
import Tooltip from "./common/Tooltip";

type StatusCardProps = {
  label: string;
  value: string;
  icon?: ReactNode;
  tone?: "info" | "good" | "warning";
  helpText?: string;
};

export default function StatusCard({
  label,
  value,
  icon,
  tone = "info",
  helpText,
}: StatusCardProps) {
  const { isDark } = useTheme();

  const cardToneClass = tone === "good"
    ? isDark
      ? "border-emerald-700/70 bg-gradient-to-br from-emerald-950/35 via-slate-900/90 to-slate-900/85"
      : "border-emerald-200 bg-gradient-to-br from-emerald-50/85 via-white/95 to-emerald-50/40"
    : tone === "warning"
      ? isDark
        ? "border-amber-700/70 bg-gradient-to-br from-amber-950/30 via-slate-900/90 to-slate-900/85"
        : "border-amber-200 bg-gradient-to-br from-amber-50/85 via-white/95 to-amber-50/35"
      : isDark
        ? "border-sky-700/70 bg-gradient-to-br from-sky-950/30 via-slate-900/90 to-slate-900/85"
        : "border-sky-200 bg-gradient-to-br from-sky-50/85 via-white/95 to-emerald-50/30";

  const valueToneClass = isDark
    ? "border-slate-600 bg-slate-800/85 text-slate-100"
    : "border-slate-200 bg-white/95 text-slate-900";

  const iconToneClass = tone === "good"
    ? isDark
      ? "border-emerald-600/70 bg-emerald-950/45 text-emerald-200"
      : "border-emerald-200 bg-white/95 text-emerald-700"
    : tone === "warning"
      ? isDark
        ? "border-amber-600/70 bg-amber-950/45 text-amber-200"
        : "border-amber-200 bg-white/95 text-amber-700"
      : isDark
        ? "border-sky-600/70 bg-sky-950/45 text-sky-200"
        : "border-sky-200 bg-white/95 text-sky-700";

  const toneDotClass = tone === "good"
    ? "bg-emerald-500"
    : tone === "warning"
      ? "bg-amber-500"
      : "bg-sky-500";
  const labelClass = isDark ? "text-slate-200" : "text-slate-700";

  return (
    <article
      className={`group relative overflow-visible rounded-2xl border p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-lg ${cardToneClass}`}
    >
      <div className="pointer-events-none absolute -right-8 -top-10 h-20 w-20 rounded-full bg-white/20 blur-xl dark:bg-cyan-300/10" />
      <div className="flex items-start justify-between gap-3">
        <div className="inline-flex items-center gap-2">
          <span className={`h-2 w-2 rounded-full ${toneDotClass}`} />
          <p className={`m-0 text-xs font-semibold uppercase tracking-[0.12em] ${labelClass}`}>
            {label}
          </p>
          {helpText ? (
            <Tooltip
              content={helpText}
              ariaLabel={`More info about ${label}`}
            />
          ) : null}
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
