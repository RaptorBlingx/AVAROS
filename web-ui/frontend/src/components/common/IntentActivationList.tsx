import type { IntentState } from "../../api/types";
import { useTheme } from "./ThemeProvider";

export type IntentViewModel = IntentState & {
  allMapped: boolean;
};

type IntentActivationListProps = {
  intents: IntentViewModel[];
  savingIntent: string | null;
  bulkAction: "enable" | "disable" | null;
  readOnly?: boolean;
  onEnableAll: () => void;
  onDisableAll: () => void;
  onToggle: (intentName: string, active: boolean) => void;
};

const INTENT_LABELS: Record<string, string> = {
  "kpi.energy.per_unit": "Energy Per Unit KPI",
  "kpi.oee": "OEE KPI",
  "kpi.scrap_rate": "Scrap Rate KPI",
  "compare.energy": "Compare Energy Performance",
  "trend.scrap": "Scrap Trend",
  "trend.energy": "Energy Trend",
  "anomaly.production.check": "Production Anomaly Check",
  "whatif.temperature": "Temperature What-If",
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
    return metricName
      .replace("co2", "CO₂")
      .replace(/_/g, " ")
      .replace(/\b\w/g, (char) => char.toUpperCase());
  }
  return metricName
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

export default function IntentActivationList({
  intents,
  savingIntent,
  bulkAction,
  readOnly = false,
  onEnableAll,
  onDisableAll,
  onToggle,
}: IntentActivationListProps) {
  const { isDark } = useTheme();

  const secondaryActionButtonClass =
    "btn-brand-subtle rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60";
  const primaryActionButtonClass =
    "btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60";

  const intentCardClass = "brand-surface rounded-xl p-4";

  const metricBadgeClass = isDark
    ? "inline-flex items-center rounded-md bg-slate-700 px-2.5 py-1 text-xs font-medium text-slate-100"
    : "inline-flex items-center rounded-md bg-slate-200 px-2.5 py-1 text-xs font-medium text-slate-700";

  const mappedStatusClass = isDark
    ? "bg-emerald-900/70 text-emerald-200"
    : "bg-emerald-100 text-emerald-800";

  const needsStatusClass = isDark
    ? "bg-amber-900/70 text-amber-200"
    : "bg-amber-100 text-amber-800";

  const warningClass = isDark ? "text-amber-300" : "text-amber-700";
  const builtInStatusClass = isDark
    ? "bg-slate-700 text-slate-300"
    : "bg-slate-100 text-slate-600";

  const kpiIntents = intents.filter((intent) => intent.category === "kpi");
  const actionIntents = intents.filter((intent) => intent.category === "action");
  const systemIntents = intents.filter((intent) => intent.category === "system");

  const renderBadge = (intent: IntentViewModel) => {
    if (intent.category === "action" || intent.category === "system") {
      return (
        <span
          className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${builtInStatusClass}`}
        >
          Built-in
        </span>
      );
    }

    return (
      <span
        className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold ${
          intent.allMapped ? mappedStatusClass : needsStatusClass
        }`}
      >
        {intent.allMapped ? "Mapped" : "Needs Mapping"}
      </span>
    );
  };

  const renderIntentCard = (intent: IntentViewModel) => {
    const toggleDisabled =
      readOnly ||
      savingIntent === intent.intent_name ||
      bulkAction !== null ||
      (intent.category === "kpi" && !intent.allMapped);

    return (
      <article key={intent.intent_name} className={intentCardClass}>
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="space-y-2">
            <h3
              className={`m-0 text-base font-semibold ${
                isDark ? "text-slate-100" : "text-slate-900"
              }`}
            >
              {toIntentLabel(intent.intent_name)}
            </h3>
            <p
              className={`m-0 text-xs ${
                isDark ? "text-slate-300" : "text-slate-500"
              }`}
            >
              {intent.intent_name}
            </p>
            {intent.category === "kpi" && (
              <div className="flex flex-wrap gap-2">
                {intent.required_metrics.map((metric) => (
                  <span key={metric} className={metricBadgeClass}>
                    {toMetricLabel(metric)}
                  </span>
                ))}
              </div>
            )}
            {intent.category === "kpi" && !intent.allMapped && (
              <p className={`m-0 text-xs font-medium ${warningClass}`}>
                This intent requires metrics that haven&apos;t been mapped yet.
              </p>
            )}
          </div>

          <div className="flex items-center gap-3">
            {renderBadge(intent)}

            <button
              type="button"
              role="switch"
              aria-checked={intent.active}
              onClick={() => onToggle(intent.intent_name, !intent.active)}
              disabled={toggleDisabled}
              title={
                intent.category === "kpi" && !intent.allMapped
                  ? "Map required metrics first"
                  : undefined
              }
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
    );
  };

  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onEnableAll}
          disabled={readOnly || bulkAction !== null}
          className={primaryActionButtonClass}
        >
          {bulkAction === "enable" ? "Enabling..." : "Enable All"}
        </button>
        <button
          type="button"
          onClick={onDisableAll}
          disabled={readOnly || bulkAction !== null}
          className={secondaryActionButtonClass}
        >
          {bulkAction === "disable" ? "Disabling..." : "Disable All"}
        </button>
      </div>

      <div className="space-y-6">
        <section className="space-y-3">
          <h3 className={`m-0 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>
            KPI Queries ({kpiIntents.length})
          </h3>
          <div className="space-y-3">
            {kpiIntents.map(renderIntentCard)}
          </div>
        </section>
        <section className="space-y-3">
          <h3 className={`m-0 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>
            Device Control ({actionIntents.length})
          </h3>
          <p className={`m-0 text-xs ${isDark ? "text-slate-400" : "text-slate-500"}`}>
            Configure device endpoints in Settings - Intent Bindings.
          </p>
          <div className="space-y-3">
            {actionIntents.map(renderIntentCard)}
          </div>
        </section>
        <section className="space-y-3">
          <h3 className={`m-0 text-sm font-semibold ${isDark ? "text-slate-200" : "text-slate-700"}`}>
            System ({systemIntents.length})
          </h3>
          <div className="space-y-3">
            {systemIntents.map(renderIntentCard)}
          </div>
        </section>
      </div>
    </>
  );
}
