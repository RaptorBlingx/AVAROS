import type { ReactNode } from "react";
import type { CanonicalMetricName } from "../../api/types";
import { groupMetricOptions } from "./metricMapping";
import type { MetricMappingRow, MetricRowError } from "./metricMapping";

type MetricMappingsTableProps<TRow extends MetricMappingRow> = {
  rows: TRow[];
  errorsByRow: Record<string, MetricRowError>;
  usedMetrics: Set<CanonicalMetricName>;
  onChange: <K extends keyof MetricMappingRow>(
    id: string,
    key: K,
    value: MetricMappingRow[K],
  ) => void;
  renderActions: (row: TRow) => ReactNode;
};

const GROUPED_OPTIONS = groupMetricOptions();

export default function MetricMappingsTable<TRow extends MetricMappingRow>({
  rows,
  errorsByRow,
  usedMetrics,
  onChange,
  renderActions,
}: MetricMappingsTableProps<TRow>) {
  return (
    <div className="overflow-x-auto rounded-xl border border-slate-200">
      <table className="min-w-full border-collapse">
        <thead className="bg-slate-100">
          <tr>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">
              Metric
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">
              Endpoint
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">
              JSON Path
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">
              Unit
            </th>
            <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">
              Action
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td className="px-3 py-4 text-sm text-slate-500" colSpan={5}>
                No metric mappings configured yet.
              </td>
            </tr>
          )}
          {rows.map((row) => (
            <tr key={row.id} className="border-t border-slate-200">
              <td className="px-3 py-3 align-top">
                <select
                  value={row.canonical_metric}
                  onChange={(event) =>
                    onChange(
                      row.id,
                      "canonical_metric",
                      event.target.value as CanonicalMetricName,
                    )
                  }
                  className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
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
                {errorsByRow[row.id]?.canonical_metric && (
                  <p className="m-0 mt-1 text-xs text-red-600">
                    {errorsByRow[row.id]?.canonical_metric}
                  </p>
                )}
              </td>
              <td className="px-3 py-3 align-top">
                <input
                  type="text"
                  value={row.endpoint}
                  onChange={(event) => onChange(row.id, "endpoint", event.target.value)}
                  placeholder="/api/v1/kpis/energy"
                  className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
                />
                {errorsByRow[row.id]?.endpoint && (
                  <p className="m-0 mt-1 text-xs text-red-600">
                    {errorsByRow[row.id]?.endpoint}
                  </p>
                )}
              </td>
              <td className="px-3 py-3 align-top">
                <input
                  type="text"
                  value={row.json_path}
                  onChange={(event) => onChange(row.id, "json_path", event.target.value)}
                  placeholder="$.data.value"
                  className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
                />
                {errorsByRow[row.id]?.json_path && (
                  <p className="m-0 mt-1 text-xs text-red-600">
                    {errorsByRow[row.id]?.json_path}
                  </p>
                )}
              </td>
              <td className="px-3 py-3 align-top">
                <input
                  type="text"
                  value={row.unit}
                  onChange={(event) => onChange(row.id, "unit", event.target.value)}
                  placeholder="kWh/unit"
                  className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
                />
                {errorsByRow[row.id]?.unit && (
                  <p className="m-0 mt-1 text-xs text-red-600">
                    {errorsByRow[row.id]?.unit}
                  </p>
                )}
              </td>
              <td className="px-3 py-3 align-top">{renderActions(row)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
