import type { ReactNode } from "react";

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
  const cardToneClass =
    tone === "good"
      ? "border-emerald-300 bg-emerald-50/80"
      : tone === "warning"
      ? "border-amber-300 bg-amber-50/80"
      : "border-sky-300 bg-sky-50/80";

  const valueToneClass =
    tone === "good"
      ? "border-emerald-300 bg-emerald-100 text-emerald-900 shadow-emerald-200/70"
      : tone === "warning"
      ? "border-amber-300 bg-amber-100 text-amber-900 shadow-amber-200/70"
      : "border-sky-300 bg-sky-100 text-sky-900 shadow-sky-200/70";

  const iconToneClass =
    tone === "good"
      ? "border-emerald-300 bg-emerald-100 text-emerald-700"
      : tone === "warning"
      ? "border-amber-300 bg-amber-100 text-amber-700"
      : "border-sky-300 bg-sky-100 text-sky-700";

  return (
    <article
      className={`rounded-xl border p-4 shadow-sm transition-transform duration-200 hover:-translate-y-0.5 ${cardToneClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="m-0 text-xs font-semibold tracking-wide text-slate-600">
          {label}
        </p>
        <div className="flex relative items-center justify-center">
          <span
            className={`inline-flex opacity-50 z-20 shadow-md  h-9 w-9 items-center justify-center rounded-lg border ${iconToneClass}`}
          >
            {icon}
          </span>
          <span
            className={`inline-flex absolute opacity-50 z-30 blur-[500px] h-9 w-9 items-center justify-center rounded-lg border ${iconToneClass}`}
          >
            {icon}
          </span>
        </div>
      </div>
      <div className="mt-3">
        <span
          className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold shadow-sm ${valueToneClass}`}
        >
          {value}
        </span>
      </div>
    </article>
  );
}
