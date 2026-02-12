import type { SystemStatusResponse } from "../../api/types";

type SuccessScreenProps = {
  status: SystemStatusResponse | null;
  onGoToDashboard: () => void;
};

export default function SuccessScreen({
  status,
  onGoToDashboard,
}: SuccessScreenProps) {
  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl border border-emerald-300 bg-emerald-50 p-6 dark:border-emerald-500/40 dark:bg-emerald-900/30">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700 dark:text-emerald-300">
          Setup Complete
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-emerald-900 dark:text-emerald-100">
          AVAROS is now configured
        </h2>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {status ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Configured
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.configured ? "Yes" : "No"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-sky-100/20 p-4 dark:border-slate-700 dark:bg-slate-800">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500 dark:text-slate-400">
                Active Adapter
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.active_adapter}
              </p>
            </div>
          </div>
        ) : (
          <p className="m-0 text-sm text-slate-600 dark:text-slate-300">
            Status is being updated...
          </p>
        )}

        <div className="mt-6">
          <button
            type="button"
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
            onClick={onGoToDashboard}
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    </section>
  );
}
