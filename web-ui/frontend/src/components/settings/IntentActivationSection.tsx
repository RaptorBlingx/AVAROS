import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getIntents,
  listMetricMappings,
  setIntentActive,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { IntentState, MetricMapping } from "../../api/types";
import IntentActivationList from "../common/IntentActivationList";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import type { IntentViewModel } from "../common/IntentActivationList";

type IntentActivationSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

export default function IntentActivationSection({ onNotify }: IntentActivationSectionProps) {
  const [intents, setIntents] = useState<IntentState[]>([]);
  const [mappedMetrics, setMappedMetrics] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingIntent, setSavingIntent] = useState<string | null>(null);
  const [bulkAction, setBulkAction] = useState<"enable" | "disable" | null>(null);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [intentList, mappings] = await Promise.all([getIntents(), listMetricMappings()]);
      setIntents(intentList);
      setMappedMetrics(new Set(mappings.map((mapping: MetricMapping) => mapping.canonical_metric)));
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const intentView = useMemo<IntentViewModel[]>(
    () =>
      intents.map((intent) => ({
        ...intent,
        allMapped:
          intent.required_metrics.length === 0 ||
          intent.required_metrics.every((metric) => mappedMetrics.has(metric)),
      })),
    [intents, mappedMetrics],
  );

  const toggleIntent = useCallback(
    async (intentName: string, nextValue: boolean) => {
      setSavingIntent(intentName);
      try {
        const updated = await setIntentActive(intentName, nextValue);
        setIntents((prev) =>
          prev.map((intent) =>
            intent.intent_name === intentName ? { ...intent, active: updated.active } : intent,
          ),
        );
        onNotify("success", "Intent state updated.");
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      } finally {
        setSavingIntent(null);
      }
    },
    [onNotify],
  );

  const setAll = useCallback(
    async (active: boolean) => {
      if (intents.length === 0) return;
      setBulkAction(active ? "enable" : "disable");
      try {
        for (const intent of intents) {
          if (intent.active !== active) {
            await setIntentActive(intent.intent_name, active);
          }
        }
        setIntents((prev) => prev.map((intent) => ({ ...intent, active })));
        onNotify("success", active ? "All intents enabled." : "All intents disabled.");
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      } finally {
        setBulkAction(null);
      }
    },
    [intents, onNotify],
  );

  return (
    <section className="space-y-3">
      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading intents..." size="sm" />
        </div>
      ) : (
        <div className="reveal-in">
          {intentView.length === 0 ? (
            <EmptyState
              title="No intents available"
              message="Intent list is empty. Reload after backend intent configuration is ready."
              actionLabel="Retry"
              onAction={() => void loadData()}
            />
          ) : (
            <IntentActivationList
              intents={intentView}
              savingIntent={savingIntent}
              bulkAction={bulkAction}
              onEnableAll={() => void setAll(true)}
              onDisableAll={() => void setAll(false)}
              onToggle={(intentName, active) => void toggleIntent(intentName, active)}
            />
          )}
        </div>
      )}
    </section>
  );
}
