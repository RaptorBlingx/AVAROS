import type { ReactNode } from "react";
import type { CanonicalMetricName } from "../../api/types";
import { groupMetricOptions } from "./metricMapping";
import type { MetricMappingRow, MetricRowError } from "./metricMapping";

type MetricMappingsTableProps<TRow extends MetricMappingRow> = {
  rows: TRow[];
  errorsByRow: Record<string, MetricRowError>;
  usedMetrics: Set<CanonicalMetricName>;
  readOnly?: boolean;
  onChange: <K extends keyof MetricMappingRow>(
    id: string,
    key: K,
    value: MetricMappingRow[K],
  ) => void;
  renderActions: (row: TRow) => ReactNode;
};

const GROUPED_OPTIONS = groupMetricOptions();

function SourceBadge({ source }: { source: string }) {
  if (source !== "auto") return null;
  return (
    <span className="ml-1.5 inline-flex items-center rounded-full bg-emerald-100 px-1.5 py-0.5 text-[10px] font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
      auto
    </span>
  );
}

export default function MetricMappingsTable<TRow extends MetricMappingRow>({
  rows,
  errorsByRow,
  usedMetrics,
  readOnly = false,
  onChange,
  renderActions,
}: MetricMappingsTableProps<TRow>) {
  const renderMetricSelect = (row: TRow) => {
    const isAuto = "source" in row && (row as MetricMappingRow).source === "auto";
    return (
      <>
        <div className="flex items-center">
          <select
            value={row.canonical_metric}
            disabled={readOnly || isAuto}
            onChange={(event) =>
              onChange(
                row.id,
                "canonical_metric",
                event.target.value as CanonicalMetricName,
              )
            }
            className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          >
            {Object.entries(GROUPED_OPTIONS).map(([category, options]) => (
              <optgroup key={category} label={category}>
                {options
                  .filter(
                    (option) =>
                      option.value === row.canonical_metric ||
                      !usedMetrics.has(option.value),
                  )
                  .map((option) => (
                    <option key={option.value} value={option.value}>
                      {option.label}
                    </option>
                  ))}
              </optgroup>
            ))}
          </select>
          <SourceBadge source={"source" in row ? (row as MetricMappingRow).source : "manual"} />
        </div>
        {errorsByRow[row.id]?.canonical_metric && (
          <p className="m-0 mt-1 text-xs text-red-600">
            {errorsByRow[row.id]?.canonical_metric}
          </p>
        )}
      </>
    );
  };

  const renderEndpointInput = (row: TRow) => {
    const isAuto = "source" in row && (row as MetricMappingRow).source === "auto";
    return (
      <>
        <input
          type="text"
          value={row.endpoint}
          disabled={readOnly || isAuto}
          onChange={(event) => onChange(row.id, "endpoint", event.target.value)}
          placeholder="/api/v1/kpis/energy"
          className={`w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 ${isAuto ? "opacity-70" : ""}`}
        />
        {errorsByRow[row.id]?.endpoint && (
          <p className="m-0 mt-1 text-xs text-red-600">
            {errorsByRow[row.id]?.endpoint}
          </p>
        )}
      </>
    );
  };

  const renderJsonPathInput = (row: TRow) => {
    const isAuto = "source" in row && (row as MetricMappingRow).source === "auto";
    return (
      <>
        <input
          type="text"
          value={row.json_path}
          disabled={readOnly || isAuto}
          onChange={(event) => onChange(row.id, "json_path", event.target.value)}
          placeholder="$.data.value"
          className={`w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 ${isAuto ? "opacity-70" : ""}`}
        />
        {errorsByRow[row.id]?.json_path && (
          <p className="m-0 mt-1 text-xs text-red-600">
            {errorsByRow[row.id]?.json_path}
          </p>
        )}
      </>
    );
  };

  const renderUnitInput = (row: TRow) => {
    const isAuto = "source" in row && (row as MetricMappingRow).source === "auto";
    return (
      <>
        <input
          type="text"
          value={row.unit}
          disabled={readOnly || isAuto}
          onChange={(event) => onChange(row.id, "unit", event.target.value)}
          placeholder="kWh/unit"
          className={`w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 ${isAuto ? "opacity-70" : ""}`}
        />
        {errorsByRow[row.id]?.unit && (
          <p className="m-0 mt-1 text-xs text-red-600">
            {errorsByRow[row.id]?.unit}
          </p>
        )}
      </>
    );
  };

  return (
    <div className="rounded-xl md:brand-surface">
      {rows.length === 0 ? (
        <div className="rounded-xl border border-slate-200/80 bg-white/70 px-3 py-4 text-sm text-slate-500 dark:border-slate-700 dark:bg-slate-900/70 dark:text-slate-400 md:rounded-none md:border-0 md:bg-transparent">
          No metric mappings configured yet.
        </div>
      ) : (
        <>
          <div className="space-y-3 p-3 md:hidden">
            {rows.map((row) => (
              <article
                key={row.id}
                className="rounded-lg bg-white/70 p-3 ring-1 ring-slate-200/80 dark:bg-slate-900/70 dark:ring-slate-700/80"
              >
                <div className="space-y-3">
                  <label className="block">
                    <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      Metric
                    </span>
                    {renderMetricSelect(row)}
                  </label>

                  <label className="block">
                    <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                      Endpoint
                    </span>
                    {renderEndpointInput(row)}
                  </label>

                  <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                    <label className="block">
                      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        JSON Path
                      </span>
                      {renderJsonPathInput(row)}
                    </label>

                    <label className="block">
                      <span className="mb-1 block text-[11px] font-semibold uppercase tracking-wide text-slate-500 dark:text-slate-400">
                        Unit
                      </span>
                      {renderUnitInput(row)}
                    </label>
                  </div>

                  <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap">
                    {renderActions(row)}
                  </div>
                </div>
              </article>
            ))}
          </div>

          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full border-collapse">
              <thead className="bg-slate-100/85 dark:bg-slate-800/95">
                <tr>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    Metric
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    Endpoint
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    JSON Path
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    Unit
                  </th>
                  <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">
                    Action
                  </th>
                </tr>
              </thead>
              <tbody>
                {rows.map((row) => (
                  <tr key={row.id} className="border-t border-slate-200 dark:border-slate-700">
                    <td className="px-3 py-3 align-top">{renderMetricSelect(row)}</td>
                    <td className="px-3 py-3 align-top">{renderEndpointInput(row)}</td>
                    <td className="px-3 py-3 align-top">{renderJsonPathInput(row)}</td>
                    <td className="px-3 py-3 align-top">{renderUnitInput(row)}</td>
                    <td className="px-3 py-3 align-top">
                      <div className="flex flex-wrap items-center gap-2 whitespace-nowrap">
                        {renderActions(row)}
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </div>
  );
}
