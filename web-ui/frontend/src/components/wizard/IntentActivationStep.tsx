import { useMemo, useState } from "react";

import Tooltip from "../common/Tooltip";
import EmptyState from "../common/EmptyState";
import ErrorMessage from "../common/ErrorMessage";
import IntentActivationList from "../common/IntentActivationList";
import LoadingSpinner from "../common/LoadingSpinner";
import IntentBindingsSection from "../settings/IntentBindingsSection";
import useIntentActivation from "../../hooks/useIntentActivation";

type IntentActivationStepProps = {
  activeProfile?: string;
  onComplete: () => void;
  onSkip: () => void;
};

export default function IntentActivationStep({
  activeProfile = "mock",
  onComplete,
  onSkip,
}: IntentActivationStepProps) {
  const [error, setError] = useState("");
  const [bindingRefreshKey, setBindingRefreshKey] = useState(0);

  const {
    intentView,
    linkingSummary,
    loading,
    savingIntent,
    bulkAction,
    loadData,
    toggleIntent,
    setAll,
  } = useIntentActivation({
    errorHandler: { mode: "state", setError },
    activeProfile,
  });

  const kpiIntentReadinessByAsset = useMemo(() => {
    const importedAssets = linkingSummary?.imported_assets ?? [];
    const kpiIntents = intentView.filter((intent) => intent.category === "kpi");
    if (importedAssets.length === 0 || kpiIntents.length === 0) {
      return [];
    }
    return importedAssets.map((asset) => {
      const linkedMetrics = new Set(asset.supported_metrics);
      const readyIntents = kpiIntents.filter((intent) =>
        intent.required_metrics.every((metric) => linkedMetrics.has(metric)),
      );
      return {
        assetId: asset.asset_id,
        displayName: asset.display_name,
        mappingMode: asset.mapping_mode,
        mappingSource: asset.mapping_source,
        linkedMetricCount: asset.linked_metric_count,
        totalMetrics: asset.total_metrics,
        supportedMetrics: asset.supported_metrics,
        readyIntents,
      };
    });
  }, [intentView, linkingSummary]);

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 6 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Intent Activation
          </h2>
          <Tooltip
            content="Why is this needed? Intents enable specific AVAROS capabilities using mapped metrics."
            ariaLabel="Why intent activation is needed"
          />
        </div>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Enable or disable intents and verify required metrics are mapped.
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading intents..." size="sm" />
          </div>
        ) : (
          <>
            <div className="mb-4 rounded-xl border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
              <h3 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                Action Intent Bindings
              </h3>
              <p className="mb-3 mt-1 text-xs text-slate-600 dark:text-slate-300">
                Configure endpoints for non-metric action and system intents.
              </p>
              <IntentBindingsSection
                refreshKey={bindingRefreshKey}
                activeProfile={"wizard"}
                onNotify={(type, message) => {
                  if (type === "error") {
                    setError(message);
                  } else {
                    setBindingRefreshKey((prev) => prev + 1);
                  }
                }}
              />
            </div>

            {kpiIntentReadinessByAsset.length > 0 && (
              <div className="mb-4 rounded-xl border border-slate-200 bg-white/70 p-4 dark:border-slate-700 dark:bg-slate-900/60">
                <h3 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  KPI Intent Readiness by Asset
                </h3>
                <p className="mb-3 mt-1 text-xs text-slate-600 dark:text-slate-300">
                  Shows which assets have enough mapped metrics to activate KPI intents confidently.
                </p>
                <div className="space-y-2">
                  {kpiIntentReadinessByAsset.map((item) => (
                    <div
                      key={item.assetId}
                      className="rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700"
                    >
                      <div className="flex items-center justify-between gap-2">
                        <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {item.displayName}
                        </p>
                        <span
                          className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${
                            item.mappingMode === "energy_only"
                              ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                              : "bg-sky-100 text-sky-700 dark:bg-sky-900/40 dark:text-sky-300"
                          }`}
                        >
                          {item.readyIntents.length} KPI intents ready
                        </span>
                      </div>
                      <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                        {item.assetId} · {item.linkedMetricCount}/{item.totalMetrics} mapped · mode: {item.mappingMode} · source: {item.mappingSource}
                      </p>
                      <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                        {item.readyIntents.length > 0
                          ? item.readyIntents.map((intent) => intent.intent_name).join(", ")
                          : "No KPI intent is fully ready for this asset yet."}
                      </p>
                      <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                        Supported metrics: {item.supportedMetrics.length > 0 ? item.supportedMetrics.join(", ") : "None"}
                      </p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {error && (
              <div className="mb-4">
                <ErrorMessage
                  title="Intent activation error"
                  message={error}
                  onRetry={() => void loadData()}
                />
              </div>
            )}

            {intentView.length === 0 ? (
              <EmptyState
                title="No intents available"
                message="Intent list is empty. Retry after backend intent configuration is ready."
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
                onToggle={(intentName, active) =>
                  void toggleIntent(intentName, active)
                }
              />
            )}

            <div className="mt-6 flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
                onClick={onSkip}
              >
                Skip
              </button>
              <button
                type="button"
                className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
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
