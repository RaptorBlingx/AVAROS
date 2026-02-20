import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  listMetricMappings,
  toFriendlyErrorMessage,
  updateMetricMapping,
} from "../../api/client";
import type {
  CanonicalMetricName,
  MetricMapping,
  MetricMappingRequest,
} from "../../api/types";
import Tooltip from "../common/Tooltip";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import MetricMappingsTable from "../common/MetricMappingsTable";
import { METRIC_OPTIONS } from "../common/metricMapping";
import type { MetricMappingRow, MetricRowError } from "../common/metricMapping";

type MetricMappingStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

const EMPTY_ROW_DEFAULTS: Omit<MetricMappingRow, "id" | "canonical_metric"> = {
  endpoint: "",
  json_path: "",
  unit: "",
  transform: "",
};

function createRow(mapping: MetricMapping): MetricMappingRow {
  return {
    id: `${mapping.canonical_metric}-${Math.random().toString(36).slice(2, 9)}`,
    canonical_metric: mapping.canonical_metric,
    endpoint: mapping.endpoint,
    json_path: mapping.json_path,
    unit: mapping.unit,
    transform: mapping.transform ?? "",
  };
}

function toRequestPayload(row: MetricMappingRow): MetricMappingRequest {
  return {
    canonical_metric: row.canonical_metric,
    endpoint: row.endpoint.trim(),
    json_path: row.json_path.trim(),
    unit: row.unit.trim(),
    transform: row.transform.trim() || null,
  };
}

export default function MetricMappingStep({
  onComplete,
  onSkip,
}: MetricMappingStepProps) {
  const [rows, setRows] = useState<MetricMappingRow[]>([]);
  const [existingByMetric, setExistingByMetric] = useState<
    Partial<Record<CanonicalMetricName, MetricMapping>>
  >({});
  const [errorsByRow, setErrorsByRow] = useState<
    Record<string, MetricRowError>
  >({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const usedMetrics = useMemo(
    () => new Set(rows.map((row) => row.canonical_metric)),
    [rows],
  );

  const unMappedMetrics = useMemo(
    () => METRIC_OPTIONS.filter((option) => !usedMetrics.has(option.value)),
    [usedMetrics],
  );

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setFormError("");
    try {
      const mappings = await listMetricMappings();
      const nextRows = mappings.map(createRow);
      const nextExistingByMetric: Partial<
        Record<CanonicalMetricName, MetricMapping>
      > = {};
      for (const mapping of mappings) {
        nextExistingByMetric[mapping.canonical_metric] = mapping;
      }
      setRows(nextRows);
      setExistingByMetric(nextExistingByMetric);
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings]);

  const validateRows = useCallback(
    (targetRows: MetricMappingRow[]): boolean => {
      const nextErrors: Record<string, MetricRowError> = {};
      const metricSet = new Set<CanonicalMetricName>();

      for (const row of targetRows) {
        const rowError: MetricRowError = {};
        if (metricSet.has(row.canonical_metric)) {
          rowError.canonical_metric =
            "Duplicate metric mapping is not allowed.";
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
    },
    [],
  );

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
        ...EMPTY_ROW_DEFAULTS,
      },
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
    <K extends keyof MetricMappingRow>(
      id: string,
      key: K,
      value: MetricMappingRow[K],
    ) => {
      setRows((prev) =>
        prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)),
      );
      setErrorsByRow((prev) => {
        if (!prev[id]) return prev;
        const rowErrors = { ...prev[id] };
        delete rowErrors[key as keyof MetricRowError];
        if (Object.keys(rowErrors).length === 0) {
          const copy = { ...prev };
          delete copy[id];
          return copy;
        }
        return { ...prev, [id]: rowErrors };
      });
    },
    [],
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
        Object.keys(existingByMetric) as CanonicalMetricName[],
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
      setFormError(toFriendlyErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }, [existingByMetric, onComplete, rows, validateRows]);

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 5 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Metric Mapping
          </h2>
          <Tooltip
            content="Why is this needed? Canonical metrics must be linked to your platform fields for KPI calculations."
            ariaLabel="Why metric mapping is needed"
          />
        </div>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Map AVAROS canonical metrics to your platform API fields.
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {loading ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
            <LoadingSpinner label="Loading existing mappings..." size="sm" />
          </div>
        ) : (
          <>
            {formError && (
              <div className="mb-4">
                <ErrorMessage
                  title="Metric mappings error"
                  message={formError}
                />
              </div>
            )}

            <MetricMappingsTable
              rows={rows}
              errorsByRow={errorsByRow}
              usedMetrics={usedMetrics}
              onChange={updateRow}
              renderActions={(row) => (
                <button
                  type="button"
                  className="rounded-lg border border-red-300 bg-red-50 px-3 py-2 text-xs font-semibold text-red-800 transition hover:bg-red-100 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200 dark:hover:bg-red-900/60"
                  onClick={() => removeRow(row.id)}
                >
                  Remove
                </button>
              )}
            />

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
                onClick={addRow}
              >
                Add Mapping
              </button>
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
                onClick={onSkip}
                disabled={saving}
              >
                Skip
              </button>
              <button
                type="button"
                className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
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
