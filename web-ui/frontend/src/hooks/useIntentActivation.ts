import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getIntents,
  listMetricMappings,
  setIntentActive,
  toFriendlyErrorMessage,
} from "../api/client";
import type { IntentState, MetricMapping } from "../api/types";
import type { IntentViewModel } from "../components/common/IntentActivationList";

type ErrorHandler =
  | { mode: "notify"; onNotify: (type: "success" | "error", msg: string) => void }
  | { mode: "state"; setError: (msg: string) => void };

type UseIntentActivationOptions = {
  errorHandler: ErrorHandler;
  refreshKey?: number;
  activeProfile?: string;
};

function isKpiMapped(intent: IntentState, mapped: Set<string>): boolean {
  return (
    intent.category !== "kpi" ||
    intent.required_metrics.every((m) => mapped.has(m))
  );
}

function findEligibleIntents(
  intents: IntentState[],
  mapped: Set<string>,
  active: boolean,
): { eligible: IntentState[]; skippedKpiCount: number } {
  let skippedKpiCount = 0;
  const eligible: IntentState[] = [];

  for (const intent of intents) {
    if (intent.active === active) continue;
    if (active && intent.category === "kpi" && !isKpiMapped(intent, mapped)) {
      skippedKpiCount++;
      continue;
    }
    eligible.push(intent);
  }
  return { eligible, skippedKpiCount };
}

export default function useIntentActivation({
  errorHandler,
  refreshKey = 0,
  activeProfile = "unconfigured",
}: UseIntentActivationOptions) {
  const [intents, setIntents] = useState<IntentState[]>([]);
  const [mappedMetrics, setMappedMetrics] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(true);
  const [savingIntent, setSavingIntent] = useState<string | null>(null);
  const [bulkAction, setBulkAction] = useState<"enable" | "disable" | null>(null);

  const reportError = useCallback(
    (msg: string) => {
      if (errorHandler.mode === "notify") {
        errorHandler.onNotify("error", msg);
      } else {
        errorHandler.setError(msg);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [errorHandler.mode],
  );

  const reportSuccess = useCallback(
    (msg: string) => {
      if (errorHandler.mode === "notify") {
        errorHandler.onNotify("success", msg);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [errorHandler.mode],
  );

  const loadData = useCallback(async () => {
    setLoading(true);
    setSavingIntent(null);
    setBulkAction(null);
    if (errorHandler.mode === "state") errorHandler.setError("");
    try {
      const [intentList, mappings] = await Promise.all([
        getIntents(),
        listMetricMappings(),
      ]);
      setIntents(intentList);
      setMappedMetrics(
        new Set(mappings.map((m: MetricMapping) => m.canonical_metric)),
      );
    } catch (err: unknown) {
      reportError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reportError]);

  useEffect(() => {
    void loadData();
  }, [loadData, refreshKey, activeProfile]);

  const isUnconfiguredProfile = useMemo(
    () => activeProfile === "unconfigured",
    [activeProfile],
  );

  const intentView = useMemo<IntentViewModel[]>(
    () =>
      intents.map((intent) => ({
        ...intent,
        allMapped: isKpiMapped(intent, mappedMetrics),
      })),
    [intents, mappedMetrics],
  );

  const toggleIntent = useCallback(
    async (intentName: string, nextValue: boolean) => {
      if (isUnconfiguredProfile) return;
      const intent = intents.find((i) => i.intent_name === intentName);
      if (intent && !isKpiMapped(intent, mappedMetrics)) return;
      setSavingIntent(intentName);
      if (errorHandler.mode === "state") errorHandler.setError("");
      try {
        const updated = await setIntentActive(intentName, nextValue);
        setIntents((prev) =>
          prev.map((i) =>
            i.intent_name === intentName ? { ...i, active: updated.active } : i,
          ),
        );
        reportSuccess("Intent state updated.");
      } catch (err: unknown) {
        reportError(toFriendlyErrorMessage(err));
      } finally {
        setSavingIntent(null);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [intents, isUnconfiguredProfile, mappedMetrics, reportError, reportSuccess],
  );

  const setAll = useCallback(
    async (active: boolean) => {
      if (isUnconfiguredProfile || intents.length === 0) return;
      setBulkAction(active ? "enable" : "disable");
      if (errorHandler.mode === "state") errorHandler.setError("");
      try {
        const { eligible, skippedKpiCount } = findEligibleIntents(
          intents,
          mappedMetrics,
          active,
        );
        for (const intent of eligible) {
          await setIntentActive(intent.intent_name, active);
        }
        const names = new Set(eligible.map((i) => i.intent_name));
        setIntents((prev) =>
          prev.map((i) => (names.has(i.intent_name) ? { ...i, active } : i)),
        );
        const message =
          active && skippedKpiCount > 0
            ? `Enabled eligible intents. ${skippedKpiCount} KPI intents still need metric mappings.`
            : active
              ? "All intents enabled."
              : "All intents disabled.";
        reportSuccess(message);
      } catch (err: unknown) {
        reportError(toFriendlyErrorMessage(err));
      } finally {
        setBulkAction(null);
      }
    },
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [isUnconfiguredProfile, intents, mappedMetrics, reportError, reportSuccess],
  );

  return {
    intentView,
    loading,
    savingIntent,
    bulkAction,
    isUnconfiguredProfile,
    loadData,
    toggleIntent,
    setAll,
  };
}
