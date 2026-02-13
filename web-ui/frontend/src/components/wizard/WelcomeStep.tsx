import type { SystemStatusResponse } from "../../api/types";
import Tooltip from "../common/Tooltip";
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
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          First-Run Wizard
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h1 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Welcome to AVAROS Setup
          </h1>
          <Tooltip
            content="Why is this needed? The wizard helps operators configure AVAROS safely with guided steps."
            ariaLabel="Why setup wizard is needed"
          />
        </div>
        <p className="mb-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          This guided setup configures your platform connection in a few quick
          steps.
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
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
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
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
