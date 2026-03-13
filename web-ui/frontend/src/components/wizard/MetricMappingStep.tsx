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
} from "../../api/types";
import useMetricMappingTest from "../../hooks/useMetricMappingTest";
import Tooltip from "../common/Tooltip";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import MetricMappingsTable from "../common/MetricMappingsTable";
import { METRIC_OPTIONS } from "../common/metricMapping";
import type { MetricMappingRow, MetricRowError } from "../common/metricMapping";
import MetricMappingRowActions from "./MetricMappingRowActions";
import {
  createWizardRow,
  EMPTY_WIZARD_ROW_DEFAULTS,
  toMappingRequestPayload,
} from "./metricMappingStep.helpers";

type MetricMappingStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

function isMetricMappingNotFoundError(error: unknown): boolean {
  if (!error || typeof error !== "object") {
    return false;
  }

  const maybeStatus = (error as { status?: unknown }).status;
  if (maybeStatus === 404) {
    return true;
  }

  const message =
    error instanceof Error
      ? error.message
      : String((error as { message?: unknown }).message ?? "");
  return message.toLowerCase().includes("metric mapping not found");
}

export default function MetricMappingStep({
  onComplete,
  onSkip,
}: MetricMappingStepProps) {
  const [rows, setRows] = useState<MetricMappingRow[]>([]);
  const [existingByMetric, setExistingByMetric] = useState<Partial<Record<CanonicalMetricName, MetricMapping>>>({});
  const [errorsByRow, setErrorsByRow] = useState<Record<string, MetricRowError>>({});
  const [formError, setFormError] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const usedMetrics = useMemo(() => new Set(rows.map((row) => row.canonical_metric)), [rows]);
  const unMappedMetrics = useMemo(() => METRIC_OPTIONS.filter((option) => !usedMetrics.has(option.value)), [usedMetrics]);
  const canAddRow = unMappedMetrics.length > 0;

  const resolveRow = useCallback((rowId: string) => rows.find((row) => row.id === rowId), [rows]);

  const {
    testStateByRow,
    testRowMapping,
    resetRowTestState,
    clearAllTestState,
  } = useMetricMappingTest({
    resolveRow,
  });

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setFormError("");
    try {
      const mappings = await listMetricMappings();
      const nextRows = mappings.map(createWizardRow);
      const nextExistingByMetric: Partial<
        Record<CanonicalMetricName, MetricMapping>
      > = {};
      for (const mapping of mappings) {
        nextExistingByMetric[mapping.canonical_metric] = mapping;
      }
      setRows(nextRows);
      setExistingByMetric(nextExistingByMetric);
      clearAllTestState();
    } catch (error: unknown) {
      setFormError(toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [clearAllTestState]);

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
    if (!canAddRow) {
      return;
    }
    const metric = unMappedMetrics[0].value;
    setRows((prev) => [
      ...prev,
      {
        id: `${metric}-${Date.now()}`,
        canonical_metric: metric,
        ...EMPTY_WIZARD_ROW_DEFAULTS,
      },
    ]);
  }, [canAddRow, unMappedMetrics]);

  const removeRow = useCallback((id: string) => {
    setRows((prev) => prev.filter((row) => row.id !== id));
    setErrorsByRow((prev) => {
      const copy = { ...prev };
      delete copy[id];
      return copy;
    });
    resetRowTestState(id);
  }, [resetRowTestState]);

  const updateRow = useCallback(
    <K extends keyof MetricMappingRow>(
      id: string,
      key: K,
      value: MetricMappingRow[K],
    ) => {
      setRows((prev) =>
        prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)),
      );
      if (
        key === "endpoint" ||
        key === "json_path" ||
        key === "canonical_metric"
      ) {
        resetRowTestState(id);
      }
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
    [resetRowTestState],
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
        const payload = toMappingRequestPayload(row);
        if (!existingByMetric[row.canonical_metric]) {
          await createMetricMapping(payload);
        } else {
          try {
            await updateMetricMapping(row.canonical_metric, payload);
          } catch (error: unknown) {
            if (!isMetricMappingNotFoundError(error)) {
              throw error;
            }
            await createMetricMapping(payload);
          }
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
          Step 4 of 6
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
                <MetricMappingRowActions
                  rowId={row.id}
                  metricName={row.canonical_metric}
                  rowTestState={testStateByRow[row.id]}
                  onTest={(rowId) => {
                    void testRowMapping(rowId);
                  }}
                  onRemove={removeRow}
                />
              )}
            />

            <div className="mt-4 flex flex-wrap gap-3">
              <button
                type="button"
                className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                onClick={addRow}
                disabled={saving || !canAddRow}
                title={canAddRow ? undefined : "All canonical metrics are already mapped."}
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
