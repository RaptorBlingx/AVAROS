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
      ? "border-emerald-200 bg-gradient-to-br from-emerald-50 to-white"
      : tone === "warning"
      ? "border-amber-200 bg-gradient-to-br from-amber-50 to-white"
      : "border-sky-200 bg-gradient-to-br from-sky-50 to-white";

  const valueToneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-100 text-emerald-900"
      : tone === "warning"
      ? "border-amber-200 bg-amber-100 text-amber-900"
      : "border-sky-200 bg-sky-100 text-sky-900";

  const iconToneClass =
    tone === "good"
      ? "border-emerald-200 bg-emerald-100 text-emerald-700"
      : tone === "warning"
      ? "border-amber-200 bg-amber-100 text-amber-700"
      : "border-sky-200 bg-sky-100 text-sky-700";

  return (
    <article
      className={`rounded-2xl border p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md ${cardToneClass}`}
    >
      <div className="flex items-start justify-between gap-3">
        <p className="m-0 text-xs font-semibold tracking-wide text-slate-600">
          {label}
        </p>
        <span
          className={`inline-flex opacity-50 h-9 w-9 items-center justify-center rounded-lg border ${iconToneClass}`}
        >
          {icon}
        </span>
      </div>
      <div className="mt-3">
        <span
          className={`inline-flex rounded-full border px-3 py-1 text-sm font-semibold ${valueToneClass}`}
        >
          {value}
        </span>
      </div>
    </article>
  );
}
