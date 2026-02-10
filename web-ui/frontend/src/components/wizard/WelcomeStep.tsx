import type { SystemStatusResponse } from "../../api/types";

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
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          First-Run Wizard
        </p>
        <h1 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
          Welcome to AVAROS Setup
        </h1>
        <p className="mb-0 mt-2 text-sm text-slate-600">
          This guided setup configures your platform connection in three quick
          steps.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {loading && (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            Loading current system status...
          </div>
        )}
        {!loading && error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
            {error}
          </div>
        )}
        {!loading && !error && status && (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-sky-100/10 p-4">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500">
                Configured
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900">
                {status.configured ? "Yes" : "No"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-sky-100/10 p-4">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500">
                Database
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900">
                {status.database_connected ? "Connected" : "Disconnected"}
              </p>
            </div>
          </div>
        )}

        <div className="mt-6">
          <button
            type="button"
            className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
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
