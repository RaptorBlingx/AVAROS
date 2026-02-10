import { useCallback, useEffect, useState } from "react";

import { getStatus } from "../../api/client";
import type { SystemStatusResponse } from "../../api/types";

type SystemInfoSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

export default function SystemInfoSection({ onNotify }: SystemInfoSectionProps) {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);

  const loadStatus = useCallback(async () => {
    setLoading(true);
    try {
      const response = await getStatus();
      setStatus(response);
    } catch (error: unknown) {
      onNotify("error", error instanceof Error ? error.message : "Failed to load system status.");
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadStatus();
  }, [loadStatus]);

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={() => void loadStatus()}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700"
        >
          Refresh
        </button>
      </header>

      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
          Loading system info...
        </div>
      ) : status ? (
        <div className="reveal-in reveal-stagger grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Active Adapter</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.active_adapter}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Loaded Intents</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.loaded_intents}</p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Database</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">
              {status.database_connected ? "Connected" : "Disconnected"}
            </p>
          </div>
          <div className="rounded-xl border border-slate-200 bg-slate-50 p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Version</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.version}</p>
          </div>
        </div>
      ) : null}
    </section>
  );
}
