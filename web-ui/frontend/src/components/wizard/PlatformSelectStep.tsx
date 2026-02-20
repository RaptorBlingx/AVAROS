import type { PlatformType } from "../../api/types";
import Tooltip from "../common/Tooltip";

type PlatformSelectStepProps = {
  value: PlatformType | null;
  onChange: (value: PlatformType) => void;
  onConfirm: () => void;
};

const OPTIONS: Array<{
  value: PlatformType;
  title: string;
  description: string;
}> = [
  {
    value: "mock",
    title: "Mock",
    description: "Demo mode with sample data. No external connection needed.",
  },
  {
    value: "reneryo",
    title: "RENERYO",
    description: "Connect to RENERYO manufacturing platform.",
  },
  {
    value: "custom_rest",
    title: "Custom REST",
    description: "Connect to any REST API with standard endpoints.",
  },
];

export default function PlatformSelectStep({
  value,
  onChange,
  onConfirm,
}: PlatformSelectStepProps) {
  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 2 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Select Your Platform
          </h2>
          <Tooltip
            content="Why is this needed? AVAROS adapts request/metric flows based on the selected platform type."
            ariaLabel="Why platform selection is needed"
          />
        </div>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <div className="grid gap-3">
          {OPTIONS.map((option) => {
            const active = value === option.value;
            return (
              <button
                key={option.value}
                type="button"
                className={`rounded-xl border p-4 text-left transition ${
                  active
                    ? "border-cyan-300 bg-gradient-to-r from-sky-50/90 via-white to-emerald-50/70 shadow-sm dark:border-cyan-500/50 dark:from-sky-900/50 dark:via-slate-900/90 dark:to-emerald-900/35"
                    : "border-slate-200 bg-white/90 hover:bg-gradient-to-r hover:from-sky-50 hover:to-emerald-50 dark:border-slate-700 dark:bg-slate-800/85 dark:hover:from-slate-800 dark:hover:via-slate-800 dark:hover:to-slate-700/90"
                }`}
                onClick={() => onChange(option.value)}
              >
                <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  {option.title}
                </p>
                <p className="m-0 mt-1 text-sm text-slate-600 dark:text-slate-300">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>
        <div className="mt-6">
          <button
            type="button"
            onClick={onConfirm}
            disabled={!value}
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-50"
          >
            Select & Continue
          </button>
        </div>
      </div>
    </section>
  );
}
