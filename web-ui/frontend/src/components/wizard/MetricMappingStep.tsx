import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createMetricMapping,
  deleteMetricMapping,
  getAssetLinkingSummary,
  importGeneratorMapping,
  listMetricMappings,
  toFriendlyErrorMessage,
  updateMetricMapping,
} from "../../api/client";
import type {
  AssetLinkingSummaryResponse,
  CanonicalMetricName,
  MetricMapping,
  MetricCoverageItem,
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
import { loadWizardPreset } from "./wizardPreset";

type MetricMappingStepProps = {
  integrationPreset?: "reneryo" | "mock" | null;
  profileName?: string;
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
  integrationPreset = null,
  profileName,
  onComplete,
  onSkip,
}: MetricMappingStepProps) {
  const isReneryoHelper = integrationPreset === "reneryo";
  const [rows, setRows] = useState<MetricMappingRow[]>([]);
  const [existingByMetric, setExistingByMetric] = useState<Partial<Record<CanonicalMetricName, MetricMapping>>>({});
  const [metricCoverage, setMetricCoverage] = useState<MetricCoverageItem[]>([]);
  const [importedAssets, setImportedAssets] = useState<
    AssetLinkingSummaryResponse["imported_assets"]
  >([]);
  const [unlinkedRegisteredAssets, setUnlinkedRegisteredAssets] = useState<
    AssetLinkingSummaryResponse["unlinked_assets"]
  >([]);
  const [discoveredAssets, setDiscoveredAssets] = useState<
    AssetLinkingSummaryResponse["discovered_assets"]
  >([]);
  const [errorsByRow, setErrorsByRow] = useState<Record<string, MetricRowError>>({});
  const [formError, setFormError] = useState("");
  const [helperError, setHelperError] = useState("");
  const [helperLoading, setHelperLoading] = useState(false);
  const [helperImporting, setHelperImporting] = useState(false);
  const [helperMappingText, setHelperMappingText] = useState("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);

  const usedMetrics = useMemo(() => new Set(rows.map((row) => row.canonical_metric)), [rows]);
  const unMappedMetrics = useMemo(() => METRIC_OPTIONS.filter((option) => !usedMetrics.has(option.value)), [usedMetrics]);
  const canAddRow = unMappedMetrics.length > 0;
  const fullKpiAssets = useMemo(
    () => importedAssets.filter((asset) => asset.mapping_mode === "full_kpi"),
    [importedAssets],
  );
  const energyOnlyAssets = useMemo(
    () => importedAssets.filter((asset) => asset.mapping_mode === "energy_only"),
    [importedAssets],
  );
  const registrationOnlyAssets = useMemo(
    () => unlinkedRegisteredAssets.filter((asset) => asset.mapping_mode === "registration_only"),
    [unlinkedRegisteredAssets],
  );

  const resolveRow = useCallback((rowId: string) => rows.find((row) => row.id === rowId), [rows]);

  const {
    testStateByRow,
    testRowMapping,
    resetRowTestState,
    clearAllTestState,
  } = useMetricMappingTest({
    resolveRow,
    onError: (message) => {
      setFormError(message);
    },
  });

  const refreshLinkingSummary = useCallback(async () => {
    if (!isReneryoHelper) {
      setMetricCoverage([]);
      setImportedAssets([]);
      setUnlinkedRegisteredAssets([]);
      setDiscoveredAssets([]);
      setHelperError("");
      return;
    }
    setHelperLoading(true);
    setHelperError("");
    try {
      const summary = await getAssetLinkingSummary();
      const normalizeAssets = (
        assets: AssetLinkingSummaryResponse["imported_assets"],
      ) =>
        assets.map((asset) => ({
          ...asset,
          mapping_mode:
            asset.mapping_mode ??
            (asset.linked_metric_count > 0 ? "full_kpi" : "registration_only"),
          mapping_source: asset.mapping_source ?? "manual",
          native_metrics: asset.native_metrics ?? [],
          supported_metrics: asset.supported_metrics ?? asset.linked_metrics ?? [],
        }));
      setMetricCoverage(summary.metric_coverage);
      setImportedAssets(normalizeAssets(summary.imported_assets));
      setUnlinkedRegisteredAssets(normalizeAssets(summary.unlinked_assets));
      setDiscoveredAssets(normalizeAssets(summary.discovered_assets));
    } catch (error: unknown) {
      setHelperError(toFriendlyErrorMessage(error));
      setMetricCoverage([]);
      setImportedAssets([]);
      setUnlinkedRegisteredAssets([]);
      setDiscoveredAssets([]);
    } finally {
      setHelperLoading(false);
    }
  }, [isReneryoHelper]);

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
    void refreshLinkingSummary();
  }, [loadMappings, refreshLinkingSummary]);

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

  const importHelperMapping = useCallback(async () => {
    setHelperError("");
    let parsed: unknown;
    try {
      parsed = JSON.parse(helperMappingText);
    } catch {
      setHelperError("Invalid JSON. Paste mapping_output.json content first.");
      return;
    }
    const payloadMapping =
      parsed &&
      typeof parsed === "object" &&
      "mapping" in (parsed as Record<string, unknown>) &&
      (parsed as Record<string, unknown>).mapping &&
      typeof (parsed as Record<string, unknown>).mapping === "object"
        ? ((parsed as Record<string, unknown>).mapping as Record<string, Record<string, string>>)
        : (parsed as Record<string, Record<string, string>>);

    if (!payloadMapping || typeof payloadMapping !== "object") {
      setHelperError("Payload must include a mapping object.");
      return;
    }

    setHelperImporting(true);
    try {
      await importGeneratorMapping({ mapping: payloadMapping });
      await refreshLinkingSummary();
    } catch (error: unknown) {
      setHelperError(toFriendlyErrorMessage(error));
    } finally {
      setHelperImporting(false);
    }
  }, [helperMappingText, refreshLinkingSummary]);

  const loadMappingFile = useCallback(async (file: File | null) => {
    if (!file) {
      return;
    }
    try {
      const text = await file.text();
      setHelperMappingText(text);
      setHelperError("");
    } catch {
      setHelperError("Failed to read JSON file.");
    }
  }, []);

  const [presetLoading, setPresetLoading] = useState(false);
  const [presetError, setPresetError] = useState("");

  const loadPreset = useCallback(async () => {
    setPresetLoading(true);
    setPresetError("");
    try {
      const preset = await loadWizardPreset(profileName);
      const newRows: MetricMappingRow[] = preset.metrics.mappings.map((m) => ({
        id: `${m.canonical_metric}-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
        canonical_metric: m.canonical_metric,
        endpoint: m.endpoint ?? preset.metrics.endpoint,
        json_path: m.json_path ?? preset.metrics.json_path,
        unit: m.unit,
        transform: "",
        source: "manual" as const,
      }));
      setRows(newRows);
      clearAllTestState();
      setErrorsByRow({});
      setFormError("");
    } catch (err: unknown) {
      setPresetError(err instanceof Error ? err.message : "Failed to load preset.");
    } finally {
      setPresetLoading(false);
    }
  }, [clearAllTestState, profileName]);

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 3 of 7
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

            {isReneryoHelper && (
              <div className="mb-4 rounded-xl border border-slate-300 bg-white/80 p-4 dark:border-slate-600 dark:bg-slate-800/80">
                <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                  RENERYO Helper
                </p>
                <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Optional: import mapping_output.json and review coverage while keeping manual mapping editable.
                </p>
                {helperError && (
                  <p className="m-0 mt-2 text-xs text-rose-700 dark:text-rose-300">{helperError}</p>
                )}
                <textarea
                  value={helperMappingText}
                  onChange={(event) => setHelperMappingText(event.target.value)}
                  placeholder='{"mapping": {"energy_total": {"Line-1": "uuid"}}}'
                  className="mt-3 min-h-24 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
                <div className="mt-2 flex flex-wrap gap-2">
                  <label className="btn-brand-subtle inline-flex cursor-pointer items-center rounded-lg px-3 py-1.5 text-xs font-semibold">
                    Load JSON File
                    <input
                      type="file"
                      accept="application/json"
                      className="hidden"
                      onChange={(event) => {
                        void loadMappingFile(event.target.files?.[0] ?? null);
                      }}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                    onClick={() => void importHelperMapping()}
                    disabled={helperImporting || !helperMappingText.trim()}
                  >
                    {helperImporting ? "Importing..." : "Import Mapping"}
                  </button>
                  <button
                    type="button"
                    className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                    onClick={() => void refreshLinkingSummary()}
                    disabled={helperLoading}
                  >
                    {helperLoading ? "Refreshing..." : "Refresh Status"}
                  </button>
                </div>
                {metricCoverage.length > 0 && (
                  <div className="mt-3 space-y-2">
                    {metricCoverage.map((item) => {
                      const isReady = item.linked_assets > 0;
                      const statusClass = isReady
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                        : "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300";
                      return (
                        <div
                          key={item.metric_name}
                          className="grid gap-2 rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700 md:grid-cols-5"
                        >
                          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100 md:col-span-2">
                            {item.metric_name}
                          </p>
                          <p className="m-0 text-xs text-slate-600 dark:text-slate-300 md:col-span-2">
                            Linked assets: {item.linked_assets}/{item.total_assets}
                          </p>
                          <div>
                            <span className={`inline-flex rounded-full px-2 py-1 text-xs font-semibold ${statusClass}`}>
                              {isReady ? "Available" : "Missing"}
                            </span>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}

                {fullKpiAssets.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      KPI-ready Assets (Full KPI)
                    </p>
                    {fullKpiAssets.map((asset) => (
                      <div
                        key={`imported-${asset.asset_id}`}
                        className="rounded-lg border border-emerald-200 bg-emerald-50/60 px-3 py-2 dark:border-emerald-700/60 dark:bg-emerald-900/20"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {asset.display_name}
                          </p>
                          <span className="inline-flex rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300">
                            {asset.linked_metric_count}/{asset.total_metrics} mapped
                          </span>
                        </div>
                        <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {asset.asset_id} · {asset.asset_type} · source: {asset.mapping_source}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                          Metrics: {asset.linked_metrics.length > 0 ? asset.linked_metrics.join(", ") : "None"}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {energyOnlyAssets.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      Energy-only Assets (RENERYO SEU)
                    </p>
                    {energyOnlyAssets.map((asset) => (
                      <div
                        key={`energy-only-${asset.asset_id}`}
                        className="rounded-lg border border-amber-200 bg-amber-50/60 px-3 py-2 dark:border-amber-700/50 dark:bg-amber-900/20"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {asset.display_name}
                          </p>
                          <span className="inline-flex rounded-full bg-amber-100 px-2 py-1 text-xs font-semibold text-amber-700 dark:bg-amber-900/40 dark:text-amber-300">
                            Energy only
                          </span>
                        </div>
                        <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {asset.asset_id} · {asset.asset_type} · source: {asset.mapping_source}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                          Supported metrics: {asset.supported_metrics.length > 0 ? asset.supported_metrics.join(", ") : "None"}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {registrationOnlyAssets.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      Registered Assets Without Metric Resources
                    </p>
                    {registrationOnlyAssets.map((asset) => (
                      <div
                        key={`unlinked-${asset.asset_id}`}
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900/60"
                      >
                        <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {asset.display_name}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {asset.asset_id} · {asset.asset_type}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                          Linked metrics: {asset.linked_metric_count}/{asset.total_metrics}
                        </p>
                      </div>
                    ))}
                  </div>
                )}

                {discoveredAssets.length > 0 && (
                  <div className="mt-4 space-y-2">
                    <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                      Live RENERYO Resources (Discovered)
                    </p>
                    {discoveredAssets.map((asset) => (
                      <div
                        key={`discovered-${asset.asset_id}`}
                        className="rounded-lg border border-slate-200 bg-white px-3 py-2 dark:border-slate-700 dark:bg-slate-900/60"
                      >
                        <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {asset.display_name}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                          {asset.asset_id} · {asset.asset_type}
                        </p>
                        <p className="m-0 mt-1 text-xs text-slate-600 dark:text-slate-300">
                          Discovered from live API. Import from Step 2 if you want to register this as a query asset.
                        </p>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            <div className="mb-4 rounded-xl border border-cyan-200 bg-cyan-50/60 p-3 dark:border-cyan-700/40 dark:bg-cyan-900/20">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-cyan-700 dark:text-cyan-300">
                    Quick Fill
                  </p>
                  <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                    Load all 19 metric mappings with endpoint, JSON path, and units from preset file.
                  </p>
                </div>
                <button
                  type="button"
                  className="btn-brand-primary rounded-lg px-4 py-2 text-xs font-semibold"
                  onClick={() => void loadPreset()}
                  disabled={presetLoading}
                >
                  {presetLoading ? "Loading…" : "Load Preset"}
                </button>
              </div>
              {presetError && (
                <p className="m-0 mt-2 text-xs text-rose-700 dark:text-rose-300">{presetError}</p>
              )}
            </div>

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
