import { useMemo, useState } from "react";

import type { ConnectionTestResponse } from "../../api/types";
import { useTheme } from "./ThemeProvider";

type ConnectionTestResultProps = {
  result: ConnectionTestResponse;
};

function latencyTone(latencyMs: number): "good" | "warn" | "bad" {
  if (latencyMs < 500) return "good";
  if (latencyMs <= 2000) return "warn";
  return "bad";
}

export default function ConnectionTestResult({ result }: ConnectionTestResultProps) {
  const { isDark } = useTheme();
  const [showDetails, setShowDetails] = useState(false);
  const [showResources, setShowResources] = useState(false);

  const adapterName = (result.adapter_name || "Unknown Adapter").trim();
  const message = (result.message || "Connection test completed.").trim();
  const errorCode = (result.error_code || "").trim();
  const errorDetails = (result.error_details || "").trim();
  const resources = Array.isArray(result.resources_discovered) ? result.resources_discovered : [];
  const latency = Number.isFinite(result.latency_ms) ? result.latency_ms : 0;
  const hasManyResources = resources.length > 5;
  const visibleResources = hasManyResources && !showResources ? resources.slice(0, 5) : resources;
  const tone = latencyTone(latency || 0);

  const latencyClass = useMemo(() => {
    if (tone === "good") {
      return isDark
        ? "border-emerald-500/70 bg-emerald-900/50 text-emerald-200"
        : "border-emerald-200 bg-emerald-50 text-emerald-800";
    }
    if (tone === "warn") {
      return isDark
        ? "border-amber-500/70 bg-amber-900/50 text-amber-200"
        : "border-amber-200 bg-amber-50 text-amber-800";
    }
    return isDark
      ? "border-rose-500/70 bg-rose-900/50 text-rose-200"
      : "border-rose-200 bg-rose-50 text-rose-800";
  }, [isDark, tone]);

  const panelClass = result.success
    ? isDark
      ? "border-emerald-700/70 bg-emerald-950/30"
      : "border-emerald-200 bg-emerald-50/80"
    : isDark
      ? "border-rose-700/70 bg-rose-950/30"
      : "border-rose-200 bg-rose-50/80";

  const headingClass = result.success
    ? isDark
      ? "text-emerald-200"
      : "text-emerald-900"
    : isDark
      ? "text-rose-200"
      : "text-rose-900";

  return (
    <section className={`mt-4 rounded-xl border p-4 ${panelClass}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-2">
          <span
            className={`mt-0.5 inline-flex h-6 w-6 shrink-0 items-center justify-center rounded-full border ${
              result.success
                ? isDark
                  ? "border-emerald-600/70 bg-emerald-900/70 text-emerald-200"
                  : "border-emerald-200 bg-emerald-100 text-emerald-700"
                : isDark
                  ? "border-rose-600/70 bg-rose-900/70 text-rose-200"
                  : "border-rose-200 bg-rose-100 text-rose-700"
            }`}
            aria-hidden="true"
          >
            {result.success ? "✓" : "✕"}
          </span>
          <div className="min-w-0">
            <p className={`m-0 text-sm font-semibold ${headingClass}`}>
              {adapterName}
            </p>
            <p className={`m-0 mt-1 text-sm ${isDark ? "text-slate-300" : "text-slate-700"}`}>
              {message}
            </p>
          </div>
        </div>

        <span className={`inline-flex rounded-full border px-2.5 py-1 text-xs font-semibold ${latencyClass}`}>
          {latency}ms
        </span>
      </div>

      {result.success && resources.length > 0 && (
        <div className="mt-3 rounded-lg border border-slate-200/80 bg-white/60 p-3 dark:border-slate-700 dark:bg-slate-900/40">
          <div className="mb-2 flex items-center justify-between gap-3">
            <p className={`m-0 text-xs font-semibold uppercase tracking-wide ${isDark ? "text-slate-300" : "text-slate-600"}`}>
              Discovered Resources ({resources.length})
            </p>
            {hasManyResources && (
              <button
                type="button"
                onClick={() => setShowResources((prev) => !prev)}
                className={`rounded-md border px-2 py-1 text-xs font-semibold ${
                  isDark
                    ? "border-slate-600 bg-slate-800 text-slate-200"
                    : "border-slate-300 bg-white text-slate-700"
                }`}
              >
                {showResources ? "Show less" : "Show all"}
              </button>
            )}
          </div>
          <ul className="m-0 list-none space-y-1 p-0">
            {visibleResources.map((resource) => (
              <li key={resource} className={`flex items-center gap-2 text-sm ${isDark ? "text-slate-200" : "text-slate-700"}`}>
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-sky-500" />
                <span className="break-all">{resource}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {!result.success && (errorCode || errorDetails) && (
        <div className="mt-3 space-y-2">
          {errorCode && (
            <span className={`inline-flex rounded-md border px-2 py-1 text-xs font-semibold ${
              isDark
                ? "border-rose-500/60 bg-rose-900/50 text-rose-200"
                : "border-rose-200 bg-rose-100 text-rose-700"
            }`}>
              {errorCode}
            </span>
          )}

          {errorDetails && (
            <div className="rounded-lg border border-slate-200/80 bg-white/60 p-3 dark:border-slate-700 dark:bg-slate-900/40">
              <button
                type="button"
                onClick={() => setShowDetails((prev) => !prev)}
                className={`inline-flex items-center gap-2 rounded-md border px-2 py-1 text-xs font-semibold ${
                  isDark
                    ? "border-slate-600 bg-slate-800 text-slate-200"
                    : "border-slate-300 bg-white text-slate-700"
                }`}
              >
                Technical Details
                <span>{showDetails ? "▾" : "▸"}</span>
              </button>
              {showDetails && (
                <p className={`m-0 mt-2 whitespace-pre-wrap break-words text-xs ${isDark ? "text-slate-300" : "text-slate-700"}`}>
                  {errorDetails}
                </p>
              )}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
