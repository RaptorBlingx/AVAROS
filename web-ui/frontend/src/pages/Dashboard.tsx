import { useCallback, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";
import { useNavigate } from "react-router-dom";

import { getHealth, getStatus, toFriendlyErrorMessage } from "../api/client";
import type { HealthResponse, SystemStatusResponse } from "../api/types";
import EmptyState from "../components/common/EmptyState";
import ErrorMessage from "../components/common/ErrorMessage";
import LoadingSpinner from "../components/common/LoadingSpinner";
import StatusCard from "../components/StatusCard";
import { useTheme } from "../components/common/ThemeProvider";

export default function Dashboard() {
  const navigate = useNavigate();
  const { isDark } = useTheme();
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [status, setStatus] = useState<SystemStatusResponse | null>(null);
  const [error, setError] = useState<string>("");
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [healthData, statusData] = await Promise.all([
        getHealth(),
        getStatus(),
      ]);
      const shouldRedirectToWizard =
        !import.meta.env.DEV &&
        !statusData.configured &&
        statusData.platform_type === "mock";
      if (shouldRedirectToWizard) {
        const skipRedirectUntilRaw = sessionStorage.getItem(
          "avaros_skip_wizard_until",
        );
        const skipRedirectUntil = skipRedirectUntilRaw
          ? Number(skipRedirectUntilRaw)
          : 0;
        if (skipRedirectUntil > Date.now()) {
          setHealth(healthData);
          setStatus(statusData);
          return;
        }
        sessionStorage.removeItem("avaros_skip_wizard_until");
        navigate("/wizard", { replace: true });
        return;
      }
      setHealth(healthData);
      setStatus(statusData);
    } catch (err) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [navigate]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const healthy = useMemo(() => health?.status === "ok", [health]);
  const cards = useMemo(() => {
    if (!status) {
      return [];
    }

    const boolText = (value: boolean): string => (value ? "Yes" : "No");
    const iconClass = "h-4 w-4";

    return [
      {
        label: "Configured",
        value: boolText(status.configured),
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path
              d="M5 12.5L10 17L19 8"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
      {
        label: "Active Adapter",
        value: status.active_adapter,
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <rect x="4" y="4" width="16" height="16" rx="2" strokeWidth="2" />
            <path d="M8 9h8M8 15h5" strokeWidth="2" strokeLinecap="round" />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
      {
        label: "Platform Type",
        value: status.platform_type,
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path
              d="M12 3l8 4.5v9L12 21l-8-4.5v-9L12 3z"
              strokeWidth="2"
              strokeLinejoin="round"
            />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
      {
        label: "Loaded Intents",
        value: String(status.loaded_intents),
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path
              d="M5 6h14M5 12h14M5 18h9"
              strokeWidth="2"
              strokeLinecap="round"
            />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
      {
        label: "Database Connected",
        value: boolText(status.database_connected),
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <ellipse cx="12" cy="6" rx="7" ry="3" strokeWidth="2" />
            <path d="M5 6v6c0 1.7 3.1 3 7 3s7-1.3 7-3V6" strokeWidth="2" />
            <path d="M5 12v6c0 1.7 3.1 3 7 3s7-1.3 7-3v-6" strokeWidth="2" />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
      {
        label: "Version",
        value: status.version,
        icon: (
          <svg
            className={iconClass}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
          >
            <path
              d="M12 2l2.2 4.5 5 .7-3.6 3.5.8 5-4.4-2.3-4.4 2.3.8-5L4.8 7.2l5-.7L12 2z"
              strokeWidth="1.8"
              strokeLinejoin="round"
            />
          </svg>
        ) as ReactNode,
        tone: "info",
      },
    ] as const;
  }, [status]);

  return (
    <section className="space-y-5">
      <header className="relative overflow-hidden rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <div className="pointer-events-none absolute -right-10 -top-14 h-36 w-36 rounded-full bg-sky-200/40 blur-2xl" />
        <div className="pointer-events-none absolute -bottom-16 right-16 h-28 w-28 rounded-full bg-emerald-200/40 blur-2xl" />
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="flex flex-row gap-4 relative">
            <div>
              <p className="m-0 bg-gradient-to-r from-sky-600 via-cyan-500 to-emerald-500 bg-clip-text text-xs font-bold uppercase tracking-[0.14em] text-transparent">
                AVAROS Control Center
              </p>
              <h2 className="m-0 mt-1 text-2xl font-semibold text-slate-900">
                Dashboard
              </h2>
              <p
                className={`mb-0 mt-1 text-sm opacity-80  ${
                  isDark ? "text-white" : "text-slate-600"
                }`}
              >
                Live operational summary for configuration and platform
                readiness.
              </p>
            </div>
          </div>
          <div className="flex flex-col items-end gap-2">
            {!loading && healthy && (
              <div
                className={`inline-flex items-center gap-2 rounded-lg border px-3 py-2 ${
                  isDark
                    ? "border-emerald-700 bg-gradient-to-r from-emerald-950/70 to-slate-900"
                    : "border-emerald-200 bg-gradient-to-r from-emerald-50 to-white"
                }`}
              >
                <span className="relative inline-flex h-2.5 w-2.5">
                  <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-70" />
                  <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-[0_0_10px_rgba(16,185,129,0.45)]" />
                </span>
                <p
                  className={`m-0 text-sm font-semibold ${
                    isDark ? "text-emerald-200" : "text-black/70"
                  }`}
                >
                  System Healthy
                </p>
              </div>
            )}
            {!loading && status && !status.configured && (
              <span
                className={`rounded-lg text-center border px-3 py-2 text-sm font-semibold ${
                  isDark
                    ? "border-amber-700 bg-gradient-to-r from-amber-950/70 to-slate-900 text-amber-200"
                    : "border-amber-200 bg-gradient-to-r from-amber-50 to-white text-black/50"
                }`}
              >
                Setup Required: platform configuration is not complete.
              </span>
            )}
          </div>
        </div>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
        {loading && (
          <div className="mb-4 rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 opacity-50">
            <LoadingSpinner label="Loading system status..." size="sm" />
          </div>
        )}
        {error && (
          <div className="mb-4">
            <ErrorMessage
              title="Unable to load dashboard"
              message={error}
              onRetry={() => void loadData()}
            />
          </div>
        )}
        {cards.length > 0 && (
          <div
            className={`grid gap-3 sm:grid-cols-2 xl:grid-cols-3 ${
              !loading ? "dash-cards" : ""
            }`}
          >
            {cards.map((card) => (
              <StatusCard
                key={card.label}
                label={card.label}
                value={card.value}
                icon={card.icon}
                tone={card.tone}
              />
            ))}
          </div>
        )}
        {!loading && !error && cards.length === 0 && (
          <EmptyState
            title="No status data yet"
            message="Dashboard data is empty. Try refreshing after AVAROS services are ready."
            actionLabel="Refresh"
            onAction={() => void loadData()}
          />
        )}
      </div>
    </section>
  );
}
