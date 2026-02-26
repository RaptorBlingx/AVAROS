import type { CanonicalMetricName } from "../../api/types";
import type { MetricTestState } from "../../hooks/useMetricMappingTest";

type MetricMappingRowActionsProps = {
  rowId: string;
  metricName: CanonicalMetricName;
  persisted: boolean;
  isDark: boolean;
  isMockProfile: boolean;
  savingRowId: string | null;
  rowTestState: MetricTestState | undefined;
  onSave: (rowId: string) => void;
  onTest: (rowId: string) => void;
  onRemove: (rowId: string) => void;
};

function resolveTestLabel(state: MetricTestState | undefined): string {
  if (state?.status === "loading") return "Testing...";
  if (state?.status === "success") return "✓";
  if (state?.status === "error") return "✕";
  return "Test";
}

function resolveTestTitle(state: MetricTestState | undefined): string {
  if (state?.status === "success") return `Value: ${state.value}`;
  if (state?.status === "error") return state.error;
  return "Test this mapping";
}

export default function MetricMappingRowActions({
  rowId,
  metricName,
  persisted,
  isDark,
  isMockProfile,
  savingRowId,
  rowTestState,
  onSave,
  onTest,
  onRemove,
}: MetricMappingRowActionsProps) {
  const isTesting = rowTestState?.status === "loading";
  const testLabel = resolveTestLabel(rowTestState);
  const testTitle = resolveTestTitle(rowTestState);

  return (
    <div className="flex w-full flex-col gap-2 sm:flex-row md:w-auto">
      <button
        type="button"
        onClick={() => onSave(rowId)}
        disabled={isMockProfile || savingRowId === rowId}
        className={`w-full rounded border px-2 py-1.5 text-xs font-semibold sm:w-auto md:min-w-[84px] ${
          isDark
            ? "border-slate-400 bg-white text-slate-900"
            : "border-sky-300 bg-sky-50 text-sky-700"
        }`}
      >
        {savingRowId === rowId ? "Saving..." : persisted ? "Save" : "Create"}
      </button>
      <button
        type="button"
        onClick={() => onTest(rowId)}
        disabled={isMockProfile || savingRowId === rowId || isTesting}
        title={testTitle}
        aria-label={`Test mapping for ${metricName}`}
        className={`w-full rounded border px-2 py-1.5 text-xs font-semibold sm:w-auto md:min-w-[84px] ${
          isDark
            ? "border-slate-400 bg-slate-800 text-slate-100"
            : "border-slate-300 bg-white text-slate-700"
        }`}
      >
        {testLabel}
      </button>
      <button
        type="button"
        onClick={() => onRemove(rowId)}
        disabled={isMockProfile}
        className={`w-full rounded border px-2 py-1.5 text-xs font-semibold sm:w-auto md:min-w-[84px] ${
          isDark
            ? "border-rose-400 bg-rose-950/60 text-rose-200"
            : "border-rose-300 bg-rose-50 text-rose-700"
        }`}
      >
        Remove
      </button>
    </div>
  );
}

