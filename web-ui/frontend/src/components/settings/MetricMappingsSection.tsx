import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  listMetricMappings,
  toFriendlyErrorMessage,
  updateMetricMapping,
} from "../../api/client";
import type { CanonicalMetricName } from "../../api/types";
import useMetricMappingTest from "../../hooks/useMetricMappingTest";
import MetricMappingsTable from "../common/MetricMappingsTable";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import MetricMappingRowActions from "./MetricMappingRowActions";
import {
  createSettingsRow,
  EMPTY_SETTINGS_ROW_DEFAULTS,
  type SettingsMetricRow,
} from "./metricMappingsSection.helpers";
import { useTheme } from "../common/ThemeProvider";
import { METRIC_OPTIONS } from "../common/metricMapping";
import type { MetricMappingRow, MetricRowError } from "../common/metricMapping";

type MetricMappingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  refreshKey?: number;
  activeProfile?: string;
};

export default function MetricMappingsSection({
  onNotify,
  refreshKey = 0,
  activeProfile = "mock",
}: MetricMappingsSectionProps) {
  const { isDark } = useTheme();
  const [rows, setRows] = useState<SettingsMetricRow[]>([]);
  const [errorsByRow, setErrorsByRow] = useState<Record<string, MetricRowError>>({});
  const [loading, setLoading] = useState(true);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);

  const usedMetrics = useMemo(
    () => new Set(rows.map((row) => row.canonical_metric)),
    [rows],
  );

  const isMockProfile = useMemo(
    () => activeProfile === "mock",
    [activeProfile],
  );

  const resolveRow = useCallback((rowId: string) => (
    rows.find((row) => row.id === rowId)
  ), [rows]);

  const {
    testStateByRow,
    testRowMapping,
    resetRowTestState,
    clearAllTestState,
  } = useMetricMappingTest({
    disabled: isMockProfile,
    resolveRow,
  });

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setSavingRowId(null);
    setErrorsByRow({});
    clearAllTestState();
    try {
      const mappings = await listMetricMappings();
      setRows(mappings.map(createSettingsRow));
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [clearAllTestState, onNotify]);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings, refreshKey, activeProfile]);

  const updateRow = useCallback(
    <K extends keyof SettingsMetricRow>(id: string, key: K, value: SettingsMetricRow[K]) => {
      setRows((prev) => prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)));
      if (key === "endpoint" || key === "json_path" || key === "canonical_metric") {
        resetRowTestState(id);
      }
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
    [resetRowTestState],
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
    if (isMockProfile) {
      return;
    }
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
        ...EMPTY_SETTINGS_ROW_DEFAULTS,
      },
    ]);
  }, [isMockProfile, onNotify, rows]);

  const saveRow = useCallback(async (rowId: string) => {
    if (isMockProfile) {
      return;
    }
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
      resetRowTestState(rowId);
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
  }, [isMockProfile, onNotify, resetRowTestState, rows, validateRow]);

  const removeRow = useCallback(async (rowId: string) => {
    if (isMockProfile) {
      return;
    }
    const row = rows.find((item) => item.id === rowId);
    if (!row) {
      return;
    }
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
      resetRowTestState(row.id);
      onNotify("success", "Metric mapping removed.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    }
  }, [isMockProfile, onNotify, resetRowTestState, rows]);

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={addRow}
          disabled={isMockProfile}
          className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
            isDark
              ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
              : "border-slate-300 bg-white text-slate-700"
          }`}
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
          {isMockProfile && (
            <div className="mb-3 rounded-lg bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              Mock profile uses built-in demo data. Metric mappings are not configurable.
            </div>
          )}
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
              readOnly={isMockProfile}
              onChange={updateBaseRow}
              renderActions={(row) => {
                return (
                  <MetricMappingRowActions
                    rowId={row.id}
                    metricName={row.canonical_metric}
                    persisted={row.persisted}
                    isDark={isDark}
                    isMockProfile={isMockProfile}
                    savingRowId={savingRowId}
                    rowTestState={testStateByRow[row.id]}
                    isAutoRow={row.source === "auto"}
                    onSave={(rowId) => {
                      void saveRow(rowId);
                    }}
                    onTest={(rowId) => {
                      void testRowMapping(rowId);
                    }}
                    onRemove={(rowId) => {
                      void removeRow(rowId);
                    }}
                  />
                );
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}
