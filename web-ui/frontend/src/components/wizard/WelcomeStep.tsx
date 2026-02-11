import type { SystemStatusResponse } from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";

type WelcomeStepProps = {
  status: SystemStatusResponse | null;
  loading: boolean;
  error: string;
  onNext: () => void;
};

export default function WelcomeStep({
  status,
  loading,
  error,
  onNext,
}: WelcomeStepProps) {
  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-slate-50/95 p-6 shadow-sm backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          First-Run Wizard
        </p>
        <h1 className="m-0 mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Welcome to AVAROS Setup
        </h1>
        <p className="mb-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          This guided setup configures your platform connection in a few quick
          steps.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-slate-50/95 p-6 shadow-sm backdrop-blur-sm dark:border-slate-700 dark:bg-slate-900">
        {loading && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading current system status..." size="sm" />
          </div>
        )}
        {!loading && error && (
          <ErrorMessage title="Status unavailable" message={error} />
        )}
        {!loading && !error && status && (
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
                Database
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900 dark:text-slate-100">
                {status.database_connected ? "Connected" : "Disconnected"}
              </p>
            </div>
          </div>
        )}

        <div className="mt-6">
          <button
            type="button"
            className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100 dark:border-sky-500/40 dark:bg-sky-900/40 dark:text-sky-200 dark:hover:bg-sky-900/60"
            onClick={onNext}
            disabled={loading || !!error}
          >
            Get Started
          </button>
        </div>
      </div>
    </section>
  );
}
