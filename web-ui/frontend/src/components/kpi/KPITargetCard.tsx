import type { KPIProgressItem } from "../../api/types";

type KPITargetCardProps = {
  metricLabel: string;
  metricHint: string;
  targetPercent: number;
  progress: KPIProgressItem | null;
};

function getTone(progress: KPIProgressItem | null, targetPercent: number): {
  text: string;
  ring: string;
  surface: string;
  panel: string;
  badge: string;
  label: string;
} {
  if (!progress) {
    return {
      text: "text-slate-600 dark:text-slate-300",
      ring: "#64748b",
      surface: "brand-surface",
      panel: "border-slate-200 bg-white/85 dark:border-slate-700 dark:bg-slate-900/55",
      badge:
        "border-slate-200 bg-slate-100 text-slate-600 dark:border-slate-700 dark:bg-slate-800 dark:text-slate-300",
      label: "No data yet",
    };
  }

  if (progress.target_met) {
    return {
      text: "text-emerald-700 dark:text-emerald-300",
      ring: "#10b981",
      surface: "brand-surface",
      panel:
        "border-emerald-200 bg-emerald-50/75 dark:border-emerald-700/50 dark:bg-emerald-950/25",
      badge:
        "border-emerald-200 bg-emerald-100 text-emerald-700 dark:border-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300",
      label: "On track",
    };
  }

  if (progress.improvement_percent > targetPercent * 0.5) {
    return {
      text: "text-amber-700 dark:text-amber-300",
      ring: "#f59e0b",
      surface: "brand-surface",
      panel: "border-amber-200 bg-amber-50/70 dark:border-amber-700/55 dark:bg-amber-950/25",
      badge:
        "border-amber-200 bg-amber-100 text-amber-700 dark:border-amber-700 dark:bg-amber-900/40 dark:text-amber-300",
      label: "At risk",
    };
  }

  return {
    text: "text-rose-700 dark:text-rose-300",
    ring: "#f43f5e",
    surface: "brand-surface",
    panel: "border-rose-200 bg-rose-50/70 dark:border-rose-700/55 dark:bg-rose-950/25",
    badge:
      "border-rose-200 bg-rose-100 text-rose-700 dark:border-rose-700 dark:bg-rose-900/40 dark:text-rose-300",
    label: "Off track",
  };
}

function getDirectionLabel(direction: string): string {
  if (!direction) {
    return "stable";
  }
  return direction.replace(/_/g, " ");
}

export default function KPITargetCard({
  metricLabel,
  metricHint,
  targetPercent,
  progress,
}: KPITargetCardProps) {
  const tone = getTone(progress, targetPercent);
  const targetAttainment = progress
    ? (progress.improvement_percent / targetPercent) * 100
    : 0;

  const safeProgressPercent = Math.max(0, Math.min(100, targetAttainment));
  const attainmentText = progress
    ? `${Math.round(targetAttainment)}%`
    : "--";

  return (
    <article className={`${tone.surface} h-full rounded-2xl p-5 shadow-sm`}>
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-slate-500 dark:text-slate-400">
            {metricLabel}
          </p>
          <p className="m-0 mt-1 text-sm text-slate-500 dark:text-slate-400">{metricHint}</p>
        </div>
        <span className={`inline-flex rounded-full border px-2 py-1 text-xs font-semibold ${tone.badge}`}>
          {tone.label}
        </span>
      </div>

      <div className="mt-4 grid grid-cols-[88px_1fr] gap-4">
        <div className={`relative flex h-[88px] w-[88px] items-center justify-center rounded-full border ${tone.panel}`}>
          <div
            className="absolute inset-1 rounded-full"
            style={{
              background: `conic-gradient(${tone.ring} ${safeProgressPercent}%, rgba(148,163,184,0.25) ${safeProgressPercent}% 100%)`,
            }}
            aria-hidden="true"
          />
          <div
            className="absolute inset-3 rounded-full bg-white dark:bg-slate-900"
            aria-hidden="true"
          />
          <span className={`relative text-sm font-semibold ${tone.text}`} title="Target attainment">
            {attainmentText}
          </span>
        </div>

        <dl className="m-0 grid grid-cols-2 gap-2 text-sm">
          <div className={`rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Baseline</dt>
            <dd className="m-0 font-semibold text-slate-900 dark:text-slate-100">
              {progress ? `${progress.baseline_value.toFixed(2)} ${progress.unit}` : "No data yet"}
            </dd>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Current</dt>
            <dd className="m-0 font-semibold text-slate-900 dark:text-slate-100">
              {progress ? `${progress.current_value.toFixed(2)} ${progress.unit}` : "No data yet"}
            </dd>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Improvement</dt>
            <dd className={`m-0 font-semibold ${tone.text}`}>
              {progress ? `${progress.improvement_percent.toFixed(2)}%` : "No data yet"}
            </dd>
          </div>
          <div className={`rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Target</dt>
            <dd className="m-0 font-semibold text-slate-900 dark:text-slate-100">{targetPercent}%</dd>
          </div>
          <div className={`col-span-2 rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Target attainment</dt>
            <dd className={`m-0 font-semibold ${tone.text}`}>
              {progress ? `${targetAttainment.toFixed(2)}%` : "No data yet"}
            </dd>
          </div>
          <div className={`col-span-2 rounded-lg border px-3 py-2 ${tone.panel}`}>
            <dt className="text-xs uppercase tracking-wide text-slate-500 dark:text-slate-400">Direction</dt>
            <dd className="m-0 font-semibold text-slate-900 dark:text-slate-100">
              {progress ? getDirectionLabel(progress.direction) : "No data yet"}
            </dd>
          </div>
        </dl>
      </div>
    </article>
  );
}
