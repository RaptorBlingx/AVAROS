import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  listMetricMappings,
  toFriendlyErrorMessage,
  updateMetricMapping,
} from "../../api/client";
import type { CanonicalMetricName, MetricMapping } from "../../api/types";
import MetricMappingsTable from "../common/MetricMappingsTable";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import { METRIC_OPTIONS } from "../common/metricMapping";
import type { MetricMappingRow, MetricRowError } from "../common/metricMapping";

type SettingsMetricRow = MetricMappingRow & {
  persisted: boolean;
  originalMetric: CanonicalMetricName | null;
};

type MetricMappingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

const EMPTY_ROW_DEFAULTS: Omit<SettingsMetricRow, "id" | "canonical_metric" | "persisted" | "originalMetric"> = {
  endpoint: "",
  json_path: "",
  unit: "",
  transform: "",
};

function createRow(mapping: MetricMapping): SettingsMetricRow {
  return {
    id: `${mapping.canonical_metric}-${Math.random().toString(36).slice(2, 9)}`,
    canonical_metric: mapping.canonical_metric,
    endpoint: mapping.endpoint,
    json_path: mapping.json_path,
    unit: mapping.unit,
    transform: mapping.transform ?? "",
    persisted: true,
    originalMetric: mapping.canonical_metric,
  };
}

export default function MetricMappingsSection({ onNotify }: MetricMappingsSectionProps) {
  const [rows, setRows] = useState<SettingsMetricRow[]>([]);
  const [errorsByRow, setErrorsByRow] = useState<Record<string, MetricRowError>>({});
  const [loading, setLoading] = useState(true);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);

  const usedMetrics = useMemo(
    () => new Set(rows.map((row) => row.canonical_metric)),
    [rows],
  );

  const loadMappings = useCallback(async () => {
    setLoading(true);
    try {
      const mappings = await listMetricMappings();
      setRows(mappings.map(createRow));
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings]);

  const updateRow = useCallback(
    <K extends keyof SettingsMetricRow>(id: string, key: K, value: SettingsMetricRow[K]) => {
      setRows((prev) => prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)));
      setErrorsByRow((prev) => {
        if (!prev[id]) return prev;
        const next = { ...prev[id] };
        delete next[key as keyof MetricRowError];
        if (Object.keys(next).length === 0) {
          const copy = { ...prev };
          delete copy[id];
          return copy;
        }
        return { ...prev, [id]: next };
      });
    },
    [],
  );

  const updateBaseRow = useCallback(
    <K extends keyof MetricMappingRow>(id: string, key: K, value: MetricMappingRow[K]) => {
      updateRow(id, key as keyof SettingsMetricRow, value as SettingsMetricRow[keyof SettingsMetricRow]);
    },
    [updateRow],
  );

  const validateRow = useCallback((row: SettingsMetricRow, allRows: SettingsMetricRow[]) => {
    const rowError: MetricRowError = {};
    if (!row.endpoint.trim()) rowError.endpoint = "Endpoint is required.";
    if (!row.json_path.trim()) rowError.json_path = "JSON path is required.";
    if (!row.unit.trim()) rowError.unit = "Unit is required.";

    const duplicateCount = allRows.filter((item) => item.canonical_metric === row.canonical_metric).length;
    if (duplicateCount > 1) {
      rowError.canonical_metric = "Duplicate metric mapping is not allowed.";
    }

    setErrorsByRow((prev) => ({ ...prev, [row.id]: rowError }));
    return Object.keys(rowError).length === 0;
  }, []);

  const addRow = useCallback(() => {
    const existing = new Set(rows.map((row) => row.canonical_metric));
    const candidate = METRIC_OPTIONS.find((option) => !existing.has(option.value));
    if (!candidate) {
      onNotify("error", "All canonical metrics are already mapped.");
      return;
    }
    setRows((prev) => [
      ...prev,
      {
        id: `${candidate.value}-${Date.now()}`,
        canonical_metric: candidate.value,
        persisted: false,
        originalMetric: null,
        ...EMPTY_ROW_DEFAULTS,
      },
    ]);
  }, [onNotify, rows]);

  const saveRow = useCallback(async (rowId: string) => {
    const row = rows.find((item) => item.id === rowId);
    if (!row) return;
    if (!validateRow(row, rows)) {
      onNotify("error", "Please fix row errors before saving.");
      return;
    }

    setSavingRowId(rowId);
    try {
      const payload = {
        canonical_metric: row.canonical_metric,
        endpoint: row.endpoint.trim(),
        json_path: row.json_path.trim(),
        unit: row.unit.trim(),
        transform: row.transform.trim() || null,
      };

      if (!row.persisted) {
        await createMetricMapping(payload);
      } else if (row.originalMetric && row.originalMetric !== row.canonical_metric) {
        await createMetricMapping(payload);
        await deleteMetricMapping(row.originalMetric);
      } else {
        await updateMetricMapping(row.canonical_metric, payload);
      }

      setRows((prev) =>
        prev.map((item) =>
          item.id === rowId
            ? { ...item, persisted: true, originalMetric: item.canonical_metric }
            : item,
        ),
      );
      setErrorsByRow((prev) => {
        const copy = { ...prev };
        delete copy[rowId];
        return copy;
      });
      onNotify("success", "Metric mapping saved.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSavingRowId(null);
    }
  }, [onNotify, rows, validateRow]);

  const removeRow = useCallback(async (row: SettingsMetricRow) => {
    try {
      if (row.persisted) {
        await deleteMetricMapping(row.originalMetric ?? row.canonical_metric);
      }
      setRows((prev) => prev.filter((item) => item.id !== row.id));
      setErrorsByRow((prev) => {
        const copy = { ...prev };
        delete copy[row.id];
        return copy;
      });
      onNotify("success", "Metric mapping removed.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    }
  }, [onNotify]);

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={addRow}
          className="rounded-lg border border-slate-300 bg-white px-3 py-1.5 text-xs font-semibold text-slate-700"
        >
          Add Mapping
        </button>
      </header>

      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading metric mappings..." size="sm" />
        </div>
      ) : (
        <div className="reveal-in">
          {rows.length === 0 ? (
            <EmptyState
              title="No metric mappings"
              message="Add a mapping to connect canonical AVAROS metrics to your platform data."
              actionLabel="Add Mapping"
              onAction={addRow}
            />
          ) : (
            <MetricMappingsTable
              rows={rows}
              errorsByRow={errorsByRow}
              usedMetrics={usedMetrics}
              onChange={updateBaseRow}
              renderActions={(row) => (
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => void saveRow(row.id)}
                    disabled={savingRowId === row.id}
                    className="rounded border border-sky-300 bg-sky-50 px-2 py-1 text-xs font-semibold text-sky-700"
                  >
                    {savingRowId === row.id ? "Saving..." : row.persisted ? "Save" : "Create"}
                  </button>
                  <button
                    type="button"
                    onClick={() => void removeRow(row)}
                    className="rounded border border-rose-300 bg-rose-50 px-2 py-1 text-xs font-semibold text-rose-700"
                  >
                    Remove
                  </button>
                </div>
              )}
            />
          )}
        </div>
      )}
    </section>
  );
}
