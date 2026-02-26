import type { CanonicalMetricName } from "../../api/types";
import type { MetricTestState } from "../../hooks/useMetricMappingTest";

type MetricMappingRowActionsProps = {
  rowId: string;
  metricName: CanonicalMetricName;
  rowTestState: MetricTestState | undefined;
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
  rowTestState,
  onTest,
  onRemove,
}: MetricMappingRowActionsProps) {
  const isTesting = rowTestState?.status === "loading";
  const testLabel = resolveTestLabel(rowTestState);
  const testTitle = resolveTestTitle(rowTestState);

  return (
    <>
      <button
        type="button"
        className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 transition hover:border-sky-300 hover:text-sky-700 disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-500 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-cyan-400 dark:hover:text-cyan-300"
        onClick={() => onTest(rowId)}
        title={testTitle}
        aria-label={`Test mapping for ${metricName}`}
        disabled={isTesting}
      >
        {testLabel}
      </button>
      <button
        type="button"
        className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800 transition hover:bg-red-100 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200 dark:hover:bg-red-900/60"
        onClick={() => onRemove(rowId)}
      >
        Remove
      </button>
    </>
  );
}

