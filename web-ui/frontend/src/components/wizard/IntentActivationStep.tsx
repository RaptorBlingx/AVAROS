import { useCallback, useEffect, useMemo, useState } from "react";

import {
  ApiError,
  getIntents,
  listMetricMappings,
  setIntentActive
} from "../../api/client";
import type { IntentState, MetricMapping } from "../../api/types";

type IntentActivationStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

const INTENT_LABELS: Record<string, string> = {
  "kpi.energy.per_unit": "Energy Per Unit KPI",
  "kpi.oee": "OEE KPI",
  "kpi.scrap_rate": "Scrap Rate KPI",
  "compare.energy": "Compare Energy Performance",
  "trend.scrap": "Scrap Trend",
  "trend.energy": "Energy Trend",
  "anomaly.production.check": "Production Anomaly Check",
  "whatif.temperature": "Temperature What-If"
};

function toIntentLabel(intentName: string): string {
  if (INTENT_LABELS[intentName]) {
    return INTENT_LABELS[intentName];
  }
  return intentName
    .split(".")
    .map((part) => part.replace(/_/g, " "))
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function toMetricLabel(metricName: string): string {
  if (metricName.startsWith("co2")) {
    return metricName.replace("co2", "CO2").replace(/_/g, " ").replace(/\b\w/g, (char) => char.toUpperCase());
  }
  return metricName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function toUserMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "Something went wrong. Please try again.";
}

export default function IntentActivationStep({
  onComplete,
  onSkip
}: IntentActivationStepProps) {
  const [intents, setIntents] = useState<IntentState[]>([]);
  const [mappedMetrics, setMappedMetrics] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingIntent, setSavingIntent] = useState<string | null>(null);
  const [bulkAction, setBulkAction] = useState<"enable" | "disable" | null>(null);
  const [error, setError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const [intentList, mappings] = await Promise.all([
        getIntents(),
        listMetricMappings()
      ]);
      setIntents(intentList);
      setMappedMetrics(new Set(mappings.map((mapping: MetricMapping) => mapping.canonical_metric)));
    } catch (err: unknown) {
      setError(toUserMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const intentStatus = useMemo(
    () =>
      intents.map((intent) => {
        const allMapped =
          intent.required_metrics.length === 0 ||
          intent.required_metrics.every((metric) => mappedMetrics.has(metric));
        return {
          ...intent,
          allMapped
        };
      }),
    [intents, mappedMetrics]
  );

  const toggleIntent = useCallback(async (intentName: string, nextValue: boolean) => {
    setSavingIntent(intentName);
    setError("");
    try {
      const updated = await setIntentActive(intentName, nextValue);
      setIntents((prev) =>
        prev.map((intent) =>
          intent.intent_name === intentName ? { ...intent, active: updated.active } : intent
        )
      );
    } catch (err: unknown) {
      setError(toUserMessage(err));
    } finally {
      setSavingIntent(null);
    }
  }, []);

  const setAll = useCallback(
    async (active: boolean) => {
      if (intents.length === 0) {
        return;
      }
      setBulkAction(active ? "enable" : "disable");
      setError("");
      try {
        for (const intent of intents) {
          if (intent.active !== active) {
            await setIntentActive(intent.intent_name, active);
          }
        }
        setIntents((prev) => prev.map((intent) => ({ ...intent, active })));
      } catch (err: unknown) {
        setError(toUserMessage(err));
      } finally {
        setBulkAction(null);
      }
    },
    [intents]
  );

  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          Step 5 of 6
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
          Intent Activation
        </h2>
        <p className="m-0 mt-2 text-sm text-slate-600">
          Enable or disable intents and verify required metrics are mapped.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            Loading intents...
          </div>
        ) : (
          <>
            {error && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
                {error}
              </div>
            )}

            <div className="mb-4 flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => void setAll(true)}
                disabled={bulkAction !== null}
                className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {bulkAction === "enable" ? "Enabling..." : "Enable All"}
              </button>
              <button
                type="button"
                onClick={() => void setAll(false)}
                disabled={bulkAction !== null}
                className="rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {bulkAction === "disable" ? "Disabling..." : "Disable All"}
              </button>
            </div>

            <div className="space-y-3">
              {intentStatus.map((intent) => (
                <article
                  key={intent.intent_name}
                  className="rounded-xl border border-slate-200 bg-slate-50 p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div className="space-y-2">
                      <h3 className="m-0 text-base font-semibold text-slate-900">
                        {toIntentLabel(intent.intent_name)}
                      </h3>
                      <p className="m-0 text-xs text-slate-500">{intent.intent_name}</p>
                      <div className="flex flex-wrap gap-2">
                        {intent.required_metrics.map((metric) => (
                          <span
                            key={metric}
                            className="inline-flex items-center rounded-md bg-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700"
                          >
                            {toMetricLabel(metric)}
                          </span>
                        ))}
                      </div>
                      {!intent.allMapped && (
                        <p className="m-0 text-xs font-medium text-amber-700">
                          This intent requires metrics that haven&apos;t been mapped yet.
                        </p>
                      )}
                    </div>

                    <div className="flex items-center gap-3">
                      <span
                        className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
                          intent.allMapped
                            ? "bg-emerald-100 text-emerald-800"
                            : "bg-amber-100 text-amber-800"
                        }`}
                      >
                        {intent.allMapped ? "Mapped" : "Needs Mapping"}
                      </span>

                      <button
                        type="button"
                        role="switch"
                        aria-checked={intent.active}
                        onClick={() =>
                          void toggleIntent(intent.intent_name, !intent.active)
                        }
                        disabled={savingIntent === intent.intent_name || bulkAction !== null}
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition ${
                          intent.active ? "bg-sky-600" : "bg-slate-300"
                        } disabled:cursor-not-allowed disabled:opacity-60`}
                      >
                        <span
                          className={`inline-block h-5 w-5 transform rounded-full bg-white transition ${
                            intent.active ? "translate-x-5" : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>
                  </div>
                </article>
              ))}
            </div>

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                onClick={onSkip}
              >
                Skip
              </button>
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100"
                onClick={onComplete}
              >
                Continue to Success
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
