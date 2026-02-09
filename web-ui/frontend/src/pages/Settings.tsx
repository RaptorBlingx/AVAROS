import { useNavigate } from "react-router-dom";

export default function Settings() {
  const navigate = useNavigate();

  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          AVAROS Control Panel
        </p>
        <h2 className="m-0 text-2xl font-semibold">Settings</h2>
        <p className="mb-0 mt-1 text-sm text-slate-500">
          Settings page coming soon. Now you can rerun the first-run wizard from
          here.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-sm text-slate-600">
          You can rerun the first-run wizard from here.
        </p>
        <button
          type="button"
          className="mt-4 inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
          onClick={() => navigate("/wizard?force=1")}
        >
          Run First-Run Wizard
        </button>
      </div>
    </section>
  );
}
