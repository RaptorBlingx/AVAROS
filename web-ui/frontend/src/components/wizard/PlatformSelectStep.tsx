import type { PlatformType } from "../../api/types";

type PlatformSelectStepProps = {
  value: PlatformType;
  onChange: (value: PlatformType) => void;
  onNext: () => void;
};

const OPTIONS: Array<{
  value: PlatformType;
  title: string;
  description: string;
}> = [
  {
    value: "mock",
    title: "Mock",
    description: "Demo mode with sample data. No external connection needed."
  },
  {
    value: "reneryo",
    title: "RENERYO",
    description: "Connect to RENERYO manufacturing platform."
  },
  {
    value: "custom_rest",
    title: "Custom REST",
    description: "Connect to any REST API with standard endpoints."
  }
];

export default function PlatformSelectStep({
  value,
  onChange,
  onNext
}: PlatformSelectStepProps) {
  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          Step 2 of 3
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
          Select Your Platform
        </h2>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="grid gap-3">
          {OPTIONS.map((option) => {
            const active = value === option.value;
            return (
              <button
                key={option.value}
                type="button"
                className={`rounded-xl border p-4 text-left transition ${
                  active
                    ? "border-sky-400 bg-sky-50"
                    : "border-slate-200 bg-white hover:bg-slate-50"
                }`}
                onClick={() => onChange(option.value)}
              >
                <p className="m-0 text-sm font-semibold text-slate-900">
                  {option.title}
                </p>
                <p className="m-0 mt-1 text-sm text-slate-600">
                  {option.description}
                </p>
              </button>
            );
          })}
        </div>

        <div className="mt-6">
          <button
            type="button"
            className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
            onClick={onNext}
          >
            Next
          </button>
        </div>
      </div>
    </section>
  );
}
