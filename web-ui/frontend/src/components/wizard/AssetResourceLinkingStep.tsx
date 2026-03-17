import { useCallback, useEffect, useMemo, useState, type ChangeEvent } from "react";

import {
  getConfiguredAssets,
  importGeneratorMapping,
  saveConfiguredAssets,
  toFriendlyErrorMessage,
} from "../../api/client";
import type { AssetMappingItem, PlatformType } from "../../api/types";
import Tooltip from "../common/Tooltip";

type AssetResourceLinkingStepProps = {
  platformType: PlatformType | null;
  onComplete: () => void;
  onSkip: () => void;
};

type LinkingRow = {
  rowId: string;
  assetId: string;
  displayName: string;
  assetType: string;
  endpointTemplate: string;
  metricResources: Record<string, string>;
};

const CANONICAL_METRICS = [
  "energy_per_unit",
  "energy_total",
  "peak_demand",
  "peak_tariff_exposure",
  "scrap_rate",
  "rework_rate",
  "material_efficiency",
  "recycled_content",
  "supplier_lead_time",
  "supplier_defect_rate",
  "supplier_on_time",
  "supplier_co2_per_kg",
  "oee",
  "throughput",
  "cycle_time",
  "changeover_time",
  "co2_per_unit",
  "co2_total",
  "co2_per_batch",
] as const;

function isObjectRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

function createRowId(seed?: string): string {
  const base = seed ? seed.replace(/[^a-zA-Z0-9_-]/g, "") : "asset";
  return `${base}-${Math.random().toString(36).slice(2, 10)}`;
}

function parseGeneratorMappingInput(
  raw: string,
): Record<string, Record<string, string>> {
  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error("Generator mapping JSON is not valid.");
  }

  const maybeWrapped = isObjectRecord(parsed) && "mapping" in parsed
    ? parsed.mapping
    : parsed;

  if (!isObjectRecord(maybeWrapped)) {
    throw new Error("Expected JSON object in generator mapping payload.");
  }

  const normalized: Record<string, Record<string, string>> = {};
  for (const [metricName, assets] of Object.entries(maybeWrapped)) {
    if (!isObjectRecord(assets)) {
      continue;
    }
    const assetMappings: Record<string, string> = {};
    for (const [assetId, resourceId] of Object.entries(assets)) {
      if (typeof assetId !== "string" || typeof resourceId !== "string") {
        continue;
      }
      const trimmedResourceId = resourceId.trim();
      if (!trimmedResourceId) {
        continue;
      }
      assetMappings[assetId] = trimmedResourceId;
    }
    if (Object.keys(assetMappings).length > 0) {
      normalized[metricName] = assetMappings;
    }
  }

  if (Object.keys(normalized).length === 0) {
    throw new Error("No valid metric-resource pairs found in mapping JSON.");
  }

  return normalized;
}

function toRows(mappings: Record<string, AssetMappingItem>): LinkingRow[] {
  return Object.entries(mappings).map(([assetId, item]) => {
    const rawMetricResources = isObjectRecord(item.metric_resources)
      ? item.metric_resources
      : {};
    const metricResources = Object.entries(rawMetricResources).reduce<Record<string, string>>(
      (acc, [metricName, resourceId]) => {
        if (typeof resourceId !== "string") {
          return acc;
        }
        const trimmed = resourceId.trim();
        if (!trimmed) {
          return acc;
        }
        acc[metricName] = trimmed;
        return acc;
      },
      {},
    );

    return {
      rowId: createRowId(assetId),
      assetId,
      displayName: String(item.display_name ?? assetId),
      assetType: String(item.asset_type ?? "machine"),
      endpointTemplate: String(item.endpoint_template ?? ""),
      metricResources,
    };
  });
}

function getMetricCoverage(metricResources: Record<string, string>): {
  linkedCount: number;
  missingMetrics: string[];
} {
  const linkedCount = CANONICAL_METRICS.reduce(
    (count, metric) => (metricResources[metric] ? count + 1 : count),
    0,
  );
  const missingMetrics = CANONICAL_METRICS.filter((metric) => !metricResources[metric]);
  return { linkedCount, missingMetrics };
}

export default function AssetResourceLinkingStep({
  platformType,
  onComplete,
  onSkip,
}: AssetResourceLinkingStepProps) {
  const resolvedPlatform = platformType ?? "custom_rest";
  const isUnconfigured = resolvedPlatform === "unconfigured";
  const isReneryo = resolvedPlatform === "reneryo";
  const isCustomRest = resolvedPlatform === "custom_rest";

  const [rows, setRows] = useState<LinkingRow[]>([]);
  const [storedMappings, setStoredMappings] = useState<
    Record<string, AssetMappingItem>
  >({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [generatorInput, setGeneratorInput] = useState("");
  const [importing, setImporting] = useState(false);
  const [importMessage, setImportMessage] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const mappingsResponse = await getConfiguredAssets();
      const mappings = mappingsResponse.asset_mappings;
      setStoredMappings(mappings);
      setRows(toRows(mappings));
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const updateEndpointTemplate = useCallback((index: number, value: string) => {
    setRows((prev) =>
      prev.map((row, rowIndex) =>
        rowIndex === index ? { ...row, endpointTemplate: value } : row,
      ),
    );
  }, []);

  const handleMappingFile = useCallback(async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    try {
      const text = await file.text();
      setGeneratorInput(text);
      setImportMessage("");
      setError("");
    } catch {
      setError("Could not read the selected mapping file.");
    } finally {
      event.target.value = "";
    }
  }, []);

  const handleImportGeneratorMapping = useCallback(async () => {
    if (!generatorInput.trim()) {
      setError("Paste mapping_output.json content or load a JSON file first.");
      return;
    }
    setImporting(true);
    setError("");
    setImportMessage("");
    try {
      const mapping = parseGeneratorMappingInput(generatorInput);
      const response = await importGeneratorMapping(mapping);
      setStoredMappings(response.asset_mappings);
      setRows(toRows(response.asset_mappings));
      setImportMessage(
        `Imported ${response.imported_resources} metric-resource links across ${Object.keys(response.asset_mappings).length} assets.`,
      );
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setImporting(false);
    }
  }, [generatorInput]);

  const saveAndContinue = useCallback(async () => {
    if (isUnconfigured || isReneryo) {
      onComplete();
      return;
    }

    setSaving(true);
    setError("");
    try {
      const payload = rows.reduce<Record<string, AssetMappingItem>>((acc, row) => {
        const assetId = row.assetId.trim();
        if (!assetId) {
          return acc;
        }
        const previous = storedMappings[assetId] ?? {};
        acc[assetId] = {
          ...previous,
          endpoint_template: row.endpointTemplate.trim(),
        };
        return acc;
      }, {});
      const response = await saveConfiguredAssets(payload);
      setStoredMappings(response.asset_mappings);
      onComplete();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [isUnconfigured, isReneryo, onComplete, rows, storedMappings]);

  const linkedCount = useMemo(
    () =>
      rows.filter((row) => {
        if (isCustomRest) {
          return row.endpointTemplate.trim().length > 0;
        }
        if (isReneryo) {
          return getMetricCoverage(row.metricResources).linkedCount > 0;
        }
        return true;
      }).length,
    [isCustomRest, isReneryo, rows],
  );

  const fullyMappedReneryoAssets = useMemo(
    () =>
      rows.filter(
        (row) =>
          getMetricCoverage(row.metricResources).linkedCount >= CANONICAL_METRICS.length,
      ).length,
    [rows],
  );

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 3 of 6
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Resource Linking
          </h2>
          <Tooltip
            content="Link registered assets to platform-specific resources for KPI retrieval."
            ariaLabel="Why resource linking is needed"
          />
        </div>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          {isUnconfigured
            ? "Unconfigured mode does not require resource linking."
            : isReneryo
            ? "Validate metric-resource coverage from generator mapping for each asset."
            : "Set endpoint templates that your API exposes for each asset."}
        </p>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        {error && (
          <div className="mb-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {error}
          </div>
        )}

        {loading ? (
          <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
            Loading registered assets...
          </div>
        ) : (
          <>
            {!isUnconfigured && (
              <div className="mb-3 rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
                Linked assets: {linkedCount}/{rows.length}
                {isReneryo && (
                  <span className="ml-2 text-xs text-slate-500 dark:text-slate-400">
                    Full coverage: {fullyMappedReneryoAssets}/{rows.length}
                  </span>
                )}
              </div>
            )}

            {isUnconfigured && (
              <div className="rounded-lg border border-sky-200 bg-sky-50 px-4 py-3 text-sm text-sky-900 dark:border-sky-500/40 dark:bg-sky-900/30 dark:text-sky-200">
                Unconfigured profile does not need additional resource linking.
              </div>
            )}

            {isReneryo && (
              <div className="mb-4 space-y-3 rounded-xl border border-slate-300 bg-white p-4 dark:border-slate-600 dark:bg-slate-800/90">
                <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                  Import / Re-import Generator Mapping
                </p>
                <p className="m-0 text-xs text-slate-600 dark:text-slate-300">
                  Use `mapping_output.json` to update metric-resource links for all assets.
                </p>
                <textarea
                  value={generatorInput}
                  onChange={(event) => setGeneratorInput(event.target.value)}
                  placeholder='{"mapping": {"energy_total": {"line-1": "uuid-1"}}}'
                  className="h-28 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 font-mono text-xs text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
                <div className="flex flex-wrap items-center gap-2">
                  <label className="btn-brand-subtle cursor-pointer rounded-lg px-3 py-2 text-sm font-semibold">
                    Load JSON File
                    <input
                      type="file"
                      accept=".json,application/json"
                      className="hidden"
                      onChange={(event) => void handleMappingFile(event)}
                    />
                  </label>
                  <button
                    type="button"
                    className="btn-brand-primary rounded-lg px-3 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
                    onClick={() => void handleImportGeneratorMapping()}
                    disabled={importing}
                  >
                    {importing ? "Importing..." : "Import Mapping"}
                  </button>
                  <button
                    type="button"
                    className="btn-brand-subtle rounded-lg px-3 py-2 text-sm font-semibold"
                    onClick={() => void load()}
                  >
                    Refresh Status
                  </button>
                </div>
                {importMessage && (
                  <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-xs text-emerald-900 dark:border-emerald-500/40 dark:bg-emerald-900/30 dark:text-emerald-200">
                    {importMessage}
                  </div>
                )}
              </div>
            )}

            {rows.length === 0 ? (
              <div className="rounded-lg border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-500/40 dark:bg-amber-900/30 dark:text-amber-200">
                No assets found. Go back and register assets first, or skip this step.
              </div>
            ) : (
              <div className="space-y-3">
                {rows.map((row, index) => {
                  const coverage = getMetricCoverage(row.metricResources);
                  const isCustomRestConfigured = row.endpointTemplate.trim().length > 0;
                  const statusLabel =
                    isCustomRest
                      ? isCustomRestConfigured
                        ? "Configured"
                        : "Pending"
                      : coverage.linkedCount >= CANONICAL_METRICS.length
                      ? "Ready"
                      : coverage.linkedCount > 0
                      ? "Partial"
                      : "Missing";
                  const statusClass =
                    statusLabel === "Ready" || statusLabel === "Configured"
                      ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-300"
                    : statusLabel === "Partial"
                      ? "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-300"
                      : "bg-rose-100 text-rose-700 dark:bg-rose-900/40 dark:text-rose-300";

                  return (
                    <div
                      key={row.rowId}
                      className="grid gap-2 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800 md:grid-cols-5"
                    >
                      <div className="md:col-span-2">
                        <p className="m-0 text-xs uppercase tracking-[0.08em] text-slate-500 dark:text-slate-400">
                          Asset
                        </p>
                        <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                          {row.displayName}
                        </p>
                        <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                          {row.assetId} · {row.assetType}
                        </p>
                      </div>

                      {isCustomRest ? (
                        <input
                          type="text"
                          value={row.endpointTemplate}
                          placeholder="/api/metrics/{asset_id}"
                          onChange={(event) =>
                            updateEndpointTemplate(index, event.target.value)
                          }
                          className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900 md:col-span-2"
                        />
                      ) : (
                        <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-900/50 dark:text-slate-200 md:col-span-2">
                          {coverage.linkedCount}/{CANONICAL_METRICS.length} metrics linked
                          {isReneryo && coverage.missingMetrics.length > 0 && (
                            <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                              Missing: {coverage.missingMetrics.slice(0, 4).join(", ")}
                              {coverage.missingMetrics.length > 4
                                ? ` +${coverage.missingMetrics.length - 4} more`
                                : ""}
                            </p>
                          )}
                        </div>
                      )}

                      <div className="flex items-center">
                        <span
                          className={`inline-flex rounded-full px-2.5 py-1 text-xs font-semibold ${statusClass}`}
                        >
                          {statusLabel}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}

            {isCustomRest && (
              <p className="m-0 mt-3 text-xs text-slate-500 dark:text-slate-400">
                Tip: Use placeholders like {"{asset_id}"} inside endpoint templates.
              </p>
            )}
          </>
        )}

        <div className="mt-6 flex flex-wrap gap-2">
          <button
            type="button"
            className="btn-brand-subtle rounded-lg px-4 py-2 text-sm font-semibold"
            onClick={onSkip}
          >
            Skip
          </button>
          <button
            type="button"
            className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => void saveAndContinue()}
            disabled={loading || saving}
          >
            {saving
              ? "Saving..."
              : isCustomRest
              ? "Save & Continue"
              : "Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
