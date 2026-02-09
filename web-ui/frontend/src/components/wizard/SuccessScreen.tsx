import type { SystemStatusResponse } from "../../api/types";

type SuccessScreenProps = {
  status: SystemStatusResponse | null;
  onGoToDashboard: () => void;
};

export default function SuccessScreen({
  status,
  onGoToDashboard
}: SuccessScreenProps) {
  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-emerald-300 bg-emerald-50 p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-emerald-700">
          Setup Complete
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-emerald-900">
          AVAROS is now configured
        </h2>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {status ? (
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500">
                Configured
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900">
                {status.configured ? "Yes" : "No"}
              </p>
            </div>
            <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
              <p className="m-0 text-xs font-semibold uppercase text-slate-500">
                Active Adapter
              </p>
              <p className="m-0 mt-2 text-lg font-semibold text-slate-900">
                {status.active_adapter}
              </p>
            </div>
          </div>
        ) : (
          <p className="m-0 text-sm text-slate-600">Status is being updated...</p>
        )}

        <div className="mt-6">
          <button
            type="button"
            className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
            onClick={onGoToDashboard}
          >
            Go to Dashboard
          </button>
        </div>
      </div>
    </section>
  );
}
