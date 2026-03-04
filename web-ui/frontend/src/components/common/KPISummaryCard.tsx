import type { ReactNode } from "react";

type KPISummaryCardProps = {
  title: string;
  description: string;
  icon: ReactNode;
  currentValue: string;
  baselineValue: string;
  improvementLabel: string;
  targetLabel: string;
  targetMet: boolean;
  directionLabel: string;
};

export default function KPISummaryCard({
  title,
  description,
  icon,
  currentValue,
  baselineValue,
  improvementLabel,
  targetLabel,
  targetMet,
  directionLabel,
}: KPISummaryCardProps) {
  return (
    <article className="brand-surface relative overflow-hidden rounded-2xl p-4">
      <div className="pointer-events-none absolute -right-8 -top-8 h-20 w-20 rounded-full bg-cyan-300/25 blur-2xl dark:bg-cyan-500/15" />
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-300">
            KPI
          </p>
          <h3 className="m-0 mt-1 text-base font-semibold text-slate-900 dark:text-slate-100">
            {title}
          </h3>
        </div>
        <span className="inline-flex h-10 w-10 items-center justify-center rounded-xl border border-sky-200 bg-white/90 text-sky-700 dark:border-sky-500/40 dark:bg-slate-900 dark:text-sky-200">
          {icon}
        </span>
      </div>

      <p className="m-0 mt-4 text-2xl font-bold text-slate-900 dark:text-slate-100">
        {currentValue}
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <span className="inline-flex rounded-full border border-sky-200 bg-sky-50 px-2.5 py-1 text-xs font-semibold text-sky-800 dark:border-sky-500/40 dark:bg-sky-900/35 dark:text-sky-200">
          {improvementLabel}
        </span>
        <span
          className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${
            targetMet
              ? "border-emerald-200 bg-emerald-50 text-emerald-800 dark:border-emerald-500/40 dark:bg-emerald-900/35 dark:text-emerald-200"
              : "border-amber-200 bg-amber-50 text-amber-800 dark:border-amber-500/40 dark:bg-amber-900/35 dark:text-amber-200"
          }`}
        >
          {targetLabel}
        </span>
      </div>

      <p className="m-0 mt-3 text-sm text-slate-600 dark:text-slate-300">{description}</p>
      <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
        Baseline: {baselineValue} • Direction: {directionLabel}
      </p>
    </article>
  );
}
