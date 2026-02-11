import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getIntents,
  listMetricMappings,
  setIntentActive,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { IntentState, MetricMapping } from "../../api/types";
import EmptyState from "../common/EmptyState";
import ErrorMessage from "../common/ErrorMessage";
import IntentActivationList from "../common/IntentActivationList";
import LoadingSpinner from "../common/LoadingSpinner";
import type { IntentViewModel } from "../common/IntentActivationList";

type IntentActivationStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

export default function IntentActivationStep({ onComplete, onSkip }: IntentActivationStepProps) {
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
      const [intentList, mappings] = await Promise.all([getIntents(), listMetricMappings()]);
      setIntents(intentList);
      setMappedMetrics(new Set(mappings.map((mapping: MetricMapping) => mapping.canonical_metric)));
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const intentStatus = useMemo<IntentViewModel[]>(
    () =>
      intents.map((intent) => ({
        ...intent,
        allMapped:
          intent.required_metrics.length === 0 ||
          intent.required_metrics.every((metric) => mappedMetrics.has(metric)),
      })),
    [intents, mappedMetrics],
  );

  const toggleIntent = useCallback(async (intentName: string, nextValue: boolean) => {
    setSavingIntent(intentName);
    setError("");
    try {
      const updated = await setIntentActive(intentName, nextValue);
      setIntents((prev) =>
        prev.map((intent) =>
          intent.intent_name === intentName ? { ...intent, active: updated.active } : intent,
        ),
      );
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
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
        setError(toFriendlyErrorMessage(err));
      } finally {
        setBulkAction(null);
      }
    },
    [intents],
  );

  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          Step 5 of 6
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">Intent Activation</h2>
        <p className="m-0 mt-2 text-sm text-slate-600">
          Enable or disable intents and verify required metrics are mapped.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading intents..." size="sm" />
          </div>
        ) : (
          <>
            {error && (
              <div className="mb-4">
                <ErrorMessage title="Intent activation error" message={error} onRetry={() => void loadData()} />
              </div>
            )}

            {intentStatus.length === 0 ? (
              <EmptyState
                title="No intents available"
                message="Intent list is empty. Retry after backend intent configuration is ready."
                actionLabel="Retry"
                onAction={() => void loadData()}
              />
            ) : (
              <IntentActivationList
                intents={intentStatus}
                savingIntent={savingIntent}
                bulkAction={bulkAction}
                onEnableAll={() => void setAll(true)}
                onDisableAll={() => void setAll(false)}
                onToggle={(intentName, active) => void toggleIntent(intentName, active)}
              />
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-sky-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-sky-50"
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
