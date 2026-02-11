import type { IntentState } from "../../api/types";

export type IntentViewModel = IntentState & {
  allMapped: boolean;
};

type IntentActivationListProps = {
  intents: IntentViewModel[];
  savingIntent: string | null;
  bulkAction: "enable" | "disable" | null;
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
  onEnableAll,
  onDisableAll,
  onToggle,
}: IntentActivationListProps) {
  return (
    <>
      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={onEnableAll}
          disabled={bulkAction !== null}
          className="rounded-lg border border-emerald-300 bg-emerald-50 px-4 py-2 text-sm font-semibold text-emerald-800 transition hover:bg-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {bulkAction === "enable" ? "Enabling..." : "Enable All"}
        </button>
        <button
          type="button"
          onClick={onDisableAll}
          disabled={bulkAction !== null}
          className="rounded-lg border border-sky-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-sky-50 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {bulkAction === "disable" ? "Disabling..." : "Disable All"}
        </button>
      </div>

      <div className="space-y-3">
        {intents.map((intent) => (
          <article
            key={intent.intent_name}
            className="rounded-xl border border-sky-200 bg-sky-50/70 p-4"
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
                  onClick={() => onToggle(intent.intent_name, !intent.active)}
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
    </>
  );
}
