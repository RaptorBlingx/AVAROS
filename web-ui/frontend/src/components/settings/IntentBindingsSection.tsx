import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createIntentBinding,
  deleteIntentBinding,
  listIntentBindings,
  toFriendlyErrorMessage,
  updateIntentBinding,
} from "../../api/client";
import type {
  IntentBinding,
  IntentBindingMethod,
  NonMetricIntentName,
} from "../../api/types";
import EmptyState from "../common/EmptyState";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";

type IntentBindingsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
  refreshKey?: number;
  activeProfile?: string;
};

type IntentBindingRow = {
  id: string;
  intent_name: NonMetricIntentName;
  endpoint: string;
  method: IntentBindingMethod;
  json_path: string;
  success_path: string;
  transform: string;
  persisted: boolean;
  originalIntent: NonMetricIntentName | null;
};

type RowErrors = {
  endpoint?: string;
  json_path?: string;
  intent_name?: string;
};

const INTENT_OPTIONS: Array<{ value: NonMetricIntentName; label: string }> = [
  { value: "control.device.turn_on", label: "Control: Turn On" },
  { value: "control.device.turn_off", label: "Control: Turn Off" },
  { value: "status.system.show", label: "Status: Show System" },
  { value: "status.profile.show", label: "Status: Show Profile" },
  { value: "help.capabilities.list", label: "Help: Capabilities" },
];

const HTTP_METHODS: IntentBindingMethod[] = ["GET", "POST", "PUT", "PATCH", "DELETE"];

const EMPTY_ROW_DEFAULTS: Omit<
  IntentBindingRow,
  "id" | "intent_name" | "persisted" | "originalIntent"
> = {
  endpoint: "",
  method: "GET",
  json_path: "",
  success_path: "",
  transform: "",
};

function createRow(binding: IntentBinding): IntentBindingRow {
  return {
    id: `${binding.intent_name}-${Math.random().toString(36).slice(2, 9)}`,
    intent_name: binding.intent_name,
    endpoint: binding.endpoint,
    method: binding.method,
    json_path: binding.json_path,
    success_path: binding.success_path ?? "",
    transform: binding.transform ?? "",
    persisted: true,
    originalIntent: binding.intent_name,
  };
}

export default function IntentBindingsSection({
  onNotify,
  refreshKey = 0,
  activeProfile = "unconfigured",
}: IntentBindingsSectionProps) {
  const { isDark } = useTheme();
  const [rows, setRows] = useState<IntentBindingRow[]>([]);
  const [errorsByRow, setErrorsByRow] = useState<Record<string, RowErrors>>({});
  const [loading, setLoading] = useState(true);
  const [savingRowId, setSavingRowId] = useState<string | null>(null);

  const isUnconfiguredProfile = useMemo(
    () => activeProfile === "unconfigured",
    [activeProfile],
  );

  const usedIntents = useMemo(
    () => new Set(rows.map((row) => row.intent_name)),
    [rows],
  );

  const loadBindings = useCallback(async () => {
    setLoading(true);
    setSavingRowId(null);
    setErrorsByRow({});
    try {
      const bindings = await listIntentBindings();
      setRows(bindings.map(createRow));
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadBindings();
  }, [loadBindings, refreshKey, activeProfile]);

  const updateRow = useCallback(
    <K extends keyof IntentBindingRow>(id: string, key: K, value: IntentBindingRow[K]) => {
      setRows((prev) => prev.map((row) => (row.id === id ? { ...row, [key]: value } : row)));
      setErrorsByRow((prev) => {
        if (!prev[id]) return prev;
        const next = { ...prev[id] };
        delete next[key as keyof RowErrors];
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

  const validateRow = useCallback((row: IntentBindingRow, allRows: IntentBindingRow[]) => {
    const rowError: RowErrors = {};
    if (!row.endpoint.trim()) rowError.endpoint = "Endpoint is required.";
    if (!row.json_path.trim()) rowError.json_path = "JSON path is required.";

    const duplicateCount = allRows.filter((item) => item.intent_name === row.intent_name).length;
    if (duplicateCount > 1) {
      rowError.intent_name = "Duplicate intent binding is not allowed.";
    }

    setErrorsByRow((prev) => ({ ...prev, [row.id]: rowError }));
    return Object.keys(rowError).length === 0;
  }, []);

  const addRow = useCallback(() => {
    if (isUnconfiguredProfile) {
      return;
    }
    const candidate = INTENT_OPTIONS.find((option) => !usedIntents.has(option.value));
    if (!candidate) {
      onNotify("error", "All non-metric intents are already bound.");
      return;
    }
    setRows((prev) => [
      ...prev,
      {
        id: `${candidate.value}-${Date.now()}`,
        intent_name: candidate.value,
        persisted: false,
        originalIntent: null,
        ...EMPTY_ROW_DEFAULTS,
      },
    ]);
  }, [isUnconfiguredProfile, onNotify, usedIntents]);

  const saveRow = useCallback(async (rowId: string) => {
    if (isUnconfiguredProfile) {
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
        intent_name: row.intent_name,
        endpoint: row.endpoint.trim(),
        method: row.method,
        json_path: row.json_path.trim(),
        success_path: row.success_path.trim() || null,
        transform: row.transform.trim() || null,
      };

      if (!row.persisted) {
        await createIntentBinding(payload);
      } else if (row.originalIntent && row.originalIntent !== row.intent_name) {
        await createIntentBinding(payload);
        await deleteIntentBinding(row.originalIntent);
      } else {
        await updateIntentBinding(row.intent_name, payload);
      }

      setRows((prev) =>
        prev.map((item) =>
          item.id === rowId
            ? { ...item, persisted: true, originalIntent: item.intent_name }
            : item,
        ),
      );
      setErrorsByRow((prev) => {
        const copy = { ...prev };
        delete copy[rowId];
        return copy;
      });
      onNotify("success", "Intent binding saved.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSavingRowId(null);
    }
  }, [isUnconfiguredProfile, onNotify, rows, validateRow]);

  const removeRow = useCallback(async (row: IntentBindingRow) => {
    if (isUnconfiguredProfile) {
      return;
    }
    try {
      if (row.persisted) {
        await deleteIntentBinding(row.originalIntent ?? row.intent_name);
      }
      setRows((prev) => prev.filter((item) => item.id !== row.id));
      setErrorsByRow((prev) => {
        const copy = { ...prev };
        delete copy[row.id];
        return copy;
      });
      onNotify("success", "Intent binding removed.");
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    }
  }, [isUnconfiguredProfile, onNotify]);

  return (
    <section className="space-y-3">
      <header className="flex items-center justify-end gap-3">
        <button
          type="button"
          onClick={addRow}
          disabled={isUnconfiguredProfile}
          className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
            isDark
              ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
              : "border-slate-300 bg-white text-slate-700"
          }`}
        >
          Add Binding
        </button>
      </header>

      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading intent bindings..." size="sm" />
        </div>
      ) : (
        <div className="reveal-in">
          {isUnconfiguredProfile && (
            <div className="mb-3 rounded-lg bg-blue-50 p-3 text-sm text-blue-700 dark:bg-blue-900/30 dark:text-blue-300">
              Unconfigured profile uses built-in demo data. Intent bindings are not configurable.
            </div>
          )}
          {rows.length === 0 ? (
            <EmptyState
              title="No intent bindings"
              message="Add a binding to map non-metric intents to your platform APIs."
              actionLabel="Add Binding"
              onAction={addRow}
            />
          ) : (
            <div className="overflow-x-auto rounded-xl md:brand-surface">
              <table className="min-w-full border-collapse">
                <thead className="bg-slate-100/85 dark:bg-slate-800/95">
                  <tr>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">Intent</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">Method</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">Endpoint</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">JSON Path</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">Success Path</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600 dark:text-slate-300">Action</th>
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row) => (
                    <tr key={row.id} className="border-t border-slate-200 dark:border-slate-700">
                      <td className="px-3 py-3 align-top min-w-[220px]">
                        <select
                          value={row.intent_name}
                          disabled={isUnconfiguredProfile}
                          onChange={(event) =>
                            updateRow(row.id, "intent_name", event.target.value as NonMetricIntentName)
                          }
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                        >
                          {INTENT_OPTIONS
                            .filter((option) => option.value === row.intent_name || !usedIntents.has(option.value))
                            .map((option) => (
                              <option key={option.value} value={option.value}>{option.label}</option>
                            ))}
                        </select>
                        {errorsByRow[row.id]?.intent_name && (
                          <p className="m-0 mt-1 text-xs text-red-600">{errorsByRow[row.id]?.intent_name}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 align-top min-w-[120px]">
                        <select
                          value={row.method}
                          disabled={isUnconfiguredProfile}
                          onChange={(event) =>
                            updateRow(row.id, "method", event.target.value as IntentBindingMethod)
                          }
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                        >
                          {HTTP_METHODS.map((method) => (
                            <option key={method} value={method}>{method}</option>
                          ))}
                        </select>
                      </td>
                      <td className="px-3 py-3 align-top min-w-[240px]">
                        <input
                          type="text"
                          value={row.endpoint}
                          disabled={isUnconfiguredProfile}
                          onChange={(event) => updateRow(row.id, "endpoint", event.target.value)}
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                        />
                        {errorsByRow[row.id]?.endpoint && (
                          <p className="m-0 mt-1 text-xs text-red-600">{errorsByRow[row.id]?.endpoint}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 align-top min-w-[220px]">
                        <input
                          type="text"
                          value={row.json_path}
                          disabled={isUnconfiguredProfile}
                          onChange={(event) => updateRow(row.id, "json_path", event.target.value)}
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                        />
                        {errorsByRow[row.id]?.json_path && (
                          <p className="m-0 mt-1 text-xs text-red-600">{errorsByRow[row.id]?.json_path}</p>
                        )}
                      </td>
                      <td className="px-3 py-3 align-top min-w-[180px]">
                        <input
                          type="text"
                          value={row.success_path}
                          disabled={isUnconfiguredProfile}
                          onChange={(event) => updateRow(row.id, "success_path", event.target.value)}
                          className="w-full rounded-lg border border-slate-300 bg-white px-2 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                        />
                      </td>
                      <td className="px-3 py-3 align-top">
                        <div className="flex w-full flex-col gap-2 sm:flex-row md:w-auto">
                          <button
                            type="button"
                            onClick={() => void saveRow(row.id)}
                            disabled={isUnconfiguredProfile || savingRowId === row.id}
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
                            onClick={() => void removeRow(row)}
                            disabled={isUnconfiguredProfile}
                            className={`w-full rounded border px-2 py-1.5 text-xs font-semibold sm:w-auto md:min-w-[84px] ${
                              isDark
                                ? "border-rose-400 bg-rose-950/60 text-rose-200"
                                : "border-rose-300 bg-rose-50 text-rose-700"
                            }`}
                          >
                            Remove
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </section>
  );
}
