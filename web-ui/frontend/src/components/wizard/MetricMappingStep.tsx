import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  listMetricMappings,
  updateMetricMapping
} from "../../api/client";
import type {
  CanonicalMetricName,
  MetricMapping,
  MetricMappingRequest
} from "../../api/types";

type MetricMappingStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

type MetricOption = {
  value: CanonicalMetricName;
  label: string;
  category: "Energy" | "Material" | "Production" | "Carbon" | "Supplier";
};

type MappingRow = {
  id: string;
  canonical_metric: CanonicalMetricName;
  endpoint: string;
  json_path: string;
  unit: string;
  transform: string;
};

type RowError = {
  canonical_metric?: string;
  endpoint?: string;
  json_path?: string;
  unit?: string;
};

const METRIC_OPTIONS: MetricOption[] = [
  { value: "energy_per_unit", label: "Energy Per Unit", category: "Energy" },
  { value: "energy_total", label: "Energy Total", category: "Energy" },
  { value: "peak_demand", label: "Peak Demand", category: "Energy" },
  {
    value: "peak_tariff_exposure",
    label: "Peak Tariff Exposure",
    category: "Energy"
  },
  { value: "scrap_rate", label: "Scrap Rate", category: "Material" },
  { value: "rework_rate", label: "Rework Rate", category: "Material" },
  {
    value: "material_efficiency",
    label: "Material Efficiency",
    category: "Material"
  },
  {
    value: "recycled_content",
    label: "Recycled Content",
    category: "Material"
  },
  { value: "oee", label: "OEE", category: "Production" },
  { value: "throughput", label: "Throughput", category: "Production" },
  { value: "cycle_time", label: "Cycle Time", category: "Production" },
  {
    value: "changeover_time",
    label: "Changeover Time",
    category: "Production"
  },
  { value: "co2_per_unit", label: "CO₂ Per Unit", category: "Carbon" },
  { value: "co2_total", label: "CO₂ Total", category: "Carbon" },
  { value: "co2_per_batch", label: "CO₂ Per Batch", category: "Carbon" },
  {
    value: "supplier_lead_time",
    label: "Supplier Lead Time",
    category: "Supplier"
  },
  {
    value: "supplier_defect_rate",
    label: "Supplier Defect Rate",
    category: "Supplier"
  },
  {
    value: "supplier_on_time",
    label: "Supplier On-Time",
    category: "Supplier"
  },
  {
    value: "supplier_co2_per_kg",
    label: "Supplier CO₂ Per kg",
    category: "Supplier"
  }
];

const EMPTY_ROW_DEFAULTS: Omit<MappingRow, "id" | "canonical_metric"> = {
  endpoint: "",
  json_path: "",
  unit: "",
  transform: ""
};

function createRow(mapping: MetricMapping): MappingRow {
  return {
    id: `${mapping.canonical_metric}-${Math.random().toString(36).slice(2, 9)}`,
    canonical_metric: mapping.canonical_metric,
    endpoint: mapping.endpoint,
    json_path: mapping.json_path,
    unit: mapping.unit,
    transform: mapping.transform ?? ""
  };
}

function toRequestPayload(row: MappingRow): MetricMappingRequest {
  return {
    canonical_metric: row.canonical_metric,
    endpoint: row.endpoint.trim(),
    json_path: row.json_path.trim(),
    unit: row.unit.trim(),
    transform: row.transform.trim() || null
  };
}

export default function MetricMappingStep({
  onComplete,
  onSkip
}: MetricMappingStepProps) {
  const [rows, setRows] = useState<MappingRow[]>([]);
  const [existingByMetric, setExistingByMetric] = useState<
    Partial<Record<CanonicalMetricName, MetricMapping>>
  >({});
  const [errorsByRow, setErrorsByRow] = useState<Record<string, RowError>>({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const usedMetrics = useMemo(
    () => new Set(rows.map((row) => row.canonical_metric)),
    [rows]
  );

  const unMappedMetrics = useMemo(
    () => METRIC_OPTIONS.filter((option) => !usedMetrics.has(option.value)),
    [usedMetrics]
  );

  const groupedOptions = useMemo(() => {
    const groups: Record<MetricOption["category"], MetricOption[]> = {
      Energy: [],
      Material: [],
      Production: [],
      Carbon: [],
      Supplier: []
    };
    for (const option of METRIC_OPTIONS) {
      groups[option.category].push(option);
    }
    return groups;
  }, []);

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setFormError("");
    try {
      const mappings = await listMetricMappings();
      const nextRows = mappings.map(createRow);
      const nextExistingByMetric: Partial<Record<CanonicalMetricName, MetricMapping>> =
        {};
      for (const mapping of mappings) {
        nextExistingByMetric[mapping.canonical_metric] = mapping;
      }
      setRows(nextRows);
      setExistingByMetric(nextExistingByMetric);
    } catch (error: unknown) {
      if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Failed to load metric mappings.");
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings]);

  const validateRows = useCallback((targetRows: MappingRow[]): boolean => {
    const nextErrors: Record<string, RowError> = {};
    const metricSet = new Set<CanonicalMetricName>();

    for (const row of targetRows) {
      const rowError: RowError = {};
      if (metricSet.has(row.canonical_metric)) {
        rowError.canonical_metric = "Duplicate metric mapping is not allowed.";
      } else {
        metricSet.add(row.canonical_metric);
      }
      if (!row.endpoint.trim()) {
        rowError.endpoint = "Endpoint is required.";
      }
      if (!row.json_path.trim()) {
        rowError.json_path = "JSON path is required.";
      }
      if (!row.unit.trim()) {
        rowError.unit = "Unit is required.";
      }
      if (Object.keys(rowError).length > 0) {
        nextErrors[row.id] = rowError;
      }
    }

    setErrorsByRow(nextErrors);
    return Object.keys(nextErrors).length === 0;
  }, []);

  const addRow = useCallback(() => {
    setFormError("");
    if (unMappedMetrics.length === 0) {
      setFormError("All canonical metrics are already mapped.");
      return;
    }
    const metric = unMappedMetrics[0].value;
    setRows((prev) => [
      ...prev,
      {
        id: `${metric}-${Date.now()}`,
        canonical_metric: metric,
        ...EMPTY_ROW_DEFAULTS
      }
    ]);
  }, [unMappedMetrics]);

  const removeRow = useCallback((id: string) => {
    setRows((prev) => prev.filter((row) => row.id !== id));
    setErrorsByRow((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
  }, []);

  const updateRow = useCallback(
    <K extends keyof MappingRow>(id: string, key: K, value: MappingRow[K]) => {
      setRows((prev) =>
        prev.map((row) => (row.id === id ? { ...row, [key]: value } : row))
      );
      setErrorsByRow((prev) => {
        if (!prev[id]) {
          return prev;
        }
        const rowErrors = { ...prev[id] };
        const errorKey = key as keyof RowError;
        delete rowErrors[errorKey];
        if (Object.keys(rowErrors).length === 0) {
          const copy = { ...prev };
          delete copy[id];
          return copy;
        }
        return { ...prev, [id]: rowErrors };
      });
    },
    []
  );

  const saveMappings = useCallback(async () => {
    setFormError("");
    if (!validateRows(rows)) {
      setFormError("Please fix validation errors before saving.");
      return;
    }

    setSaving(true);
    try {
      const targetMetrics = new Set(rows.map((row) => row.canonical_metric));
      const existingMetrics = new Set(
        Object.keys(existingByMetric) as CanonicalMetricName[]
      );

      for (const row of rows) {
        const payload = toRequestPayload(row);
        if (!existingByMetric[row.canonical_metric]) {
          await createMetricMapping(payload);
        } else {
          await updateMetricMapping(row.canonical_metric, payload);
        }
      }

      for (const metricName of existingMetrics) {
        if (!targetMetrics.has(metricName)) {
          await deleteMetricMapping(metricName);
        }
      }

      onComplete();
    } catch (error: unknown) {
      if (error instanceof Error) {
        setFormError(error.message);
      } else {
        setFormError("Failed to save metric mappings.");
      }
    } finally {
      setSaving(false);
    }
  }, [existingByMetric, onComplete, rows, validateRows]);

  return (
    <section className="space-y-4">
      <header className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700">
          Step 4 of 6
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900">
          Metric Mapping
        </h2>
        <p className="m-0 mt-2 text-sm text-slate-600">
          Map AVAROS canonical metrics to your platform API fields.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            Loading existing mappings...
          </div>
        ) : (
          <>
            {formError && (
              <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900">
                {formError}
              </div>
            )}

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
                      <td
                        className="px-3 py-4 text-sm text-slate-500"
                        colSpan={5}
                      >
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
                            updateRow(
                              row.id,
                              "canonical_metric",
                              event.target.value as CanonicalMetricName
                            )
                          }
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
                        >
                          {Object.entries(groupedOptions).map(
                            ([category, options]) => (
                              <optgroup key={category} label={category}>
                                {options
                                  .filter(
                                    (option) =>
                                      option.value === row.canonical_metric ||
                                      !usedMetrics.has(option.value)
                                  )
                                  .map((option) => (
                                    <option
                                      key={option.value}
                                      value={option.value}
                                    >
                                      {option.label}
                                    </option>
                                  ))}
                              </optgroup>
                            )
                          )}
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
                          onChange={(event) =>
                            updateRow(row.id, "endpoint", event.target.value)
                          }
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
                          onChange={(event) =>
                            updateRow(row.id, "json_path", event.target.value)
                          }
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
                          onChange={(event) =>
                            updateRow(row.id, "unit", event.target.value)
                          }
                          placeholder="kWh/unit"
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2"
                        />
                        {errorsByRow[row.id]?.unit && (
                          <p className="m-0 mt-1 text-xs text-red-600">
                            {errorsByRow[row.id]?.unit}
                          </p>
                        )}
                      </td>
                      <td className="px-3 py-3 align-top">
                        <button
                          type="button"
                          className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800 transition hover:bg-red-100"
                          onClick={() => removeRow(row.id)}
                        >
                          Remove
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                onClick={addRow}
              >
                Add Mapping
              </button>
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800 transition hover:bg-slate-50"
                onClick={onSkip}
                disabled={saving}
              >
                Skip
              </button>
              <button
                type="button"
                className="inline-flex items-center rounded-lg border border-sky-300 bg-sky-50 px-4 py-2 text-sm font-semibold text-sky-800 transition hover:bg-sky-100 disabled:cursor-not-allowed disabled:opacity-60"
                onClick={() => void saveMappings()}
                disabled={saving}
              >
                {saving ? "Saving..." : "Save Mappings & Continue"}
              </button>
            </div>
          </>
        )}
      </div>
    </section>
  );
}
