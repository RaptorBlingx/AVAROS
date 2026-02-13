import type { ReactNode } from "react";

type KPISummaryCardProps = {
  title: string;
  description: string;
  icon: ReactNode;
  statusText?: string;
};

export default function KPISummaryCard({
  title,
  description,
  icon,
  statusText = "Not yet available",
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

      <div className="mt-4 flex items-center justify-between gap-2">
        <span className="inline-flex rounded-full border border-amber-200 bg-amber-50 px-2.5 py-1 text-xs font-semibold text-amber-800 dark:border-amber-500/40 dark:bg-amber-900/35 dark:text-amber-200">
          {statusText}
        </span>
        <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-500 dark:text-slate-300">
          <svg viewBox="0 0 24 24" className="h-3.5 w-3.5" fill="none" stroke="currentColor">
            <path d="M5 16l5-5 4 4 5-7" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          Trend pending
        </span>
      </div>

      <p className="m-0 mt-3 text-sm text-slate-600 dark:text-slate-300">{description}</p>
      <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
        Configure data sources to see KPI values.
      </p>
    </article>
  );
}
