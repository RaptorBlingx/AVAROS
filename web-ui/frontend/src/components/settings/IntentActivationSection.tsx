import IntentActivationList from "../common/IntentActivationList";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import useIntentActivation from "../../hooks/useIntentActivation";

type IntentActivationSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  refreshKey?: number;
  activeProfile?: string;
};

export default function IntentActivationSection({
  onNotify,
  refreshKey = 0,
  activeProfile = "unconfigured",
}: IntentActivationSectionProps) {
  const {
    intentView,
    loading,
    savingIntent,
    bulkAction,
    isUnconfiguredProfile,
    loadData,
    toggleIntent,
    setAll,
  } = useIntentActivation({
    errorHandler: { mode: "notify", onNotify },
    refreshKey,
    activeProfile,
  });

  return (
    <section className="space-y-3">
      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading intents..." size="sm" />
        </div>
      ) : (
        <div className="reveal-in">
          {isUnconfiguredProfile && (
            <div className="mb-3 rounded-lg bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              Unconfigured profile uses built-in demo data. Intent activation is not configurable.
            </div>
          )}
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
              readOnly={isUnconfiguredProfile}
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
