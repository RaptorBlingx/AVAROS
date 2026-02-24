import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  getPlatformConfig,
  listMetricMappings,
  testMetricMapping,
  toFriendlyErrorMessage,
  updateMetricMapping,
} from "../../api/client";
import type { CanonicalMetricName, MetricMapping } from "../../api/types";
import MetricMappingsTable from "../common/MetricMappingsTable";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";
import { METRIC_OPTIONS } from "../common/metricMapping";
import type { MetricMappingRow, MetricRowError } from "../common/metricMapping";

type SettingsMetricRow = MetricMappingRow & {
  persisted: boolean;
  originalMetric: CanonicalMetricName | null;
};

type MetricTestState =
  | { status: "loading" }
  | { status: "success"; value: number }
  | { status: "error"; error: string };

type MetricMappingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  refreshKey?: number;
  activeProfile?: string;
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
  const [testStateByRow, setTestStateByRow] = useState<Record<string, MetricTestState>>({});

  const usedMetrics = useMemo(
    () => new Set(rows.map((row) => row.canonical_metric)),
    [rows],
  );

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setSavingRowId(null);
    setErrorsByRow({});
    setTestStateByRow({});
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
  }, [loadMappings, refreshKey, activeProfile]);

  const isMockProfile = useMemo(
    () => activeProfile === "mock",
    [activeProfile],
  );

  const updateRow = useCallback(
    <K extends keyof SettingsMetricRow>(id: string, key: K, value: SettingsMetricRow[K]) => {
      setRows((prev) => prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)));
      if (key === "endpoint" || key === "json_path" || key === "canonical_metric") {
        setTestStateByRow((prev) => {
          if (!prev[id]) return prev;
          const copy = { ...prev };
          delete copy[id];
          return copy;
        });
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
        ...EMPTY_ROW_DEFAULTS,
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
      setTestStateByRow((prev) => {
        if (!prev[rowId]) return prev;
        const copy = { ...prev };
        delete copy[rowId];
        return copy;
      });
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
  }, [isMockProfile, onNotify, rows, validateRow]);

  const removeRow = useCallback(async (row: SettingsMetricRow) => {
    if (isMockProfile) {
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
      setTestStateByRow((prev) => {
        if (!prev[row.id]) return prev;
        const copy = { ...prev };
        delete copy[row.id];
        return copy;
      });
      onNotify("success", "Metric mapping removed.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    }
  }, [isMockProfile, onNotify]);

  const testRow = useCallback(async (rowId: string) => {
    if (isMockProfile) {
      return;
    }
    const row = rows.find((item) => item.id === rowId);
    if (!row) {
      return;
    }
    if (!row.endpoint.trim() || !row.json_path.trim()) {
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: "Endpoint and JSON path are required before testing.",
        },
      }));
      return;
    }

    setTestStateByRow((prev) => ({ ...prev, [rowId]: { status: "loading" } }));
    try {
      const config = await getPlatformConfig();
      if (!config.api_url.trim()) {
        setTestStateByRow((prev) => ({
          ...prev,
          [rowId]: {
            status: "error",
            error: "Platform base URL is not configured yet.",
          },
        }));
        return;
      }

      const response = await testMetricMapping({
        base_url: config.api_url,
        endpoint: row.endpoint.trim(),
        json_path: row.json_path.trim(),
        auth_type: config.extra_settings.auth_type === "cookie" ? "cookie" : "bearer",
        auth_token: config.api_key,
      });
      if (response.success && typeof response.value === "number") {
        const resolvedValue = response.value;
        setTestStateByRow((prev) => ({
          ...prev,
          [rowId]: { status: "success", value: resolvedValue },
        }));
        return;
      }
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: response.error ?? "Mapping test failed.",
        },
      }));
    } catch (error: unknown) {
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: toFriendlyErrorMessage(error),
        },
      }));
    }
  }, [isMockProfile, rows]);

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
                const rowTestState = testStateByRow[row.id];
                const isTesting = rowTestState?.status === "loading";
                let testLabel = "Test";
                let testTitle = "Test this mapping";
                if (rowTestState?.status === "loading") {
                  testLabel = "Testing...";
                } else if (rowTestState?.status === "success") {
                  testLabel = "✓";
                  testTitle = `Value: ${rowTestState.value}`;
                } else if (rowTestState?.status === "error") {
                  testLabel = "✕";
                  testTitle = rowTestState.error;
                }

                return (
                  <div className="flex w-full flex-col gap-2 sm:flex-row md:w-auto">
                    <button
                      type="button"
                      onClick={() => void saveRow(row.id)}
                      disabled={isMockProfile || savingRowId === row.id}
                      className={`w-full rounded border px-2 py-1.5 text-xs font-semibold sm:w-auto md:min-w-[84px] ${
                        isDark
                          ? "border-slate-400 bg-white text-slate-900"
                          : "border-sky-300 bg-sky-50 text-sky-700"
                      }`}
                    >
                      {savingRowId === row.id ? "Saving..." : row.persisted ? "Save" : "Create"}
                    </button>
                    <button
                      type="button"
                      onClick={() => void testRow(row.id)}
                      disabled={isMockProfile || savingRowId === row.id || isTesting}
                      title={testTitle}
                      aria-label={`Test mapping for ${row.canonical_metric}`}
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
                      onClick={() => void removeRow(row)}
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
              }}
            />
          )}
        </div>
      )}
    </section>
  );
}
