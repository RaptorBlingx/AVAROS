import { useCallback, useEffect, useState } from "react";

import { getStatus, toFriendlyErrorMessage } from "../../api/client";
import type { SystemStatusResponse } from "../../api/types";
import EmptyState from "../common/EmptyState";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";

type SystemInfoSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

export default function SystemInfoSection({ onNotify }: SystemInfoSectionProps) {
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const loadStatus = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const response = await getStatus();
      setStatus(response);
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setError(message);
      onNotify("error", message);
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
          className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
        >
          Refresh
        </button>
      </header>

      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading system info..." size="sm" />
        </div>
      ) : error ? (
        <ErrorMessage
          title="System info unavailable"
          message={error}
          onRetry={() => void loadStatus()}
        />
      ) : status ? (
        <div className="reveal-in reveal-stagger grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="brand-surface rounded-xl p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Active Adapter</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.active_adapter}</p>
          </div>
          <div className="brand-surface rounded-xl p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Loaded Intents</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.loaded_intents}</p>
          </div>
          <div className="brand-surface rounded-xl p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Database</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">
              {status.database_connected ? "Connected" : "Disconnected"}
            </p>
          </div>
          <div className="brand-surface rounded-xl p-4">
            <p className="m-0 text-xs font-semibold uppercase text-slate-500">Version</p>
            <p className="m-0 mt-2 text-base font-semibold text-slate-900">{status.version}</p>
          </div>
        </div>
      ) : (
        <EmptyState
          title="No system info"
          message="System status is empty. Refresh after AVAROS services are running."
          actionLabel="Refresh"
          onAction={() => void loadStatus()}
        />
      )}
    </section>
  );
}
