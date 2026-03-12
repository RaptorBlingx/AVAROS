import { useState } from "react";

import Tooltip from "../common/Tooltip";
import EmptyState from "../common/EmptyState";
import ErrorMessage from "../common/ErrorMessage";
import IntentActivationList from "../common/IntentActivationList";
import LoadingSpinner from "../common/LoadingSpinner";
import useIntentActivation from "../../hooks/useIntentActivation";

type IntentActivationStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

export default function IntentActivationStep({
  onComplete,
  onSkip,
}: IntentActivationStepProps) {
  const [error, setError] = useState("");

  const {
    intentView,
    loading,
    savingIntent,
    bulkAction,
    loadData,
    toggleIntent,
    setAll,
  } = useIntentActivation({
    errorHandler: { mode: "state", setError },
  });

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
