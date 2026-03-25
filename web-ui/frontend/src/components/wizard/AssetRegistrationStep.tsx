import { useCallback, useEffect, useMemo, useState } from "react";

import {
  getAssetDiscovery,
  getConfiguredAssets,
  getGeneratorAssetPreview,
  saveConfiguredAssets,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  AssetMappingItem,
  NativeMetricBindings,
  PlatformType,
} from "../../api/types";
import {
  aliasesToCsv,
  csvToAliases,
  toAssetId,
} from "../settings/assetManagementSection.helpers";
import Tooltip from "../common/Tooltip";

type RegistrationRow = {
  rowId: string;
  assetId: string;
  displayName: string;
  assetType: "line" | "machine" | "sensor";
  aliases: string;
  mappingSource: "manual" | "generator" | "live_discovery";
  capabilityMode: "full_kpi" | "energy_only";
  nativeMetricBindings: NativeMetricBindings;
  isExisting: boolean;
  existingAssetId: string | null;
};

type SuggestedAsset = {
  asset_id: string;
  display_name: string;
  asset_type: "line" | "machine" | "sensor";
  aliases: string[];
  metric_count?: number;
  source: "live" | "generator";
};

type SuggestionInput = {
  asset_id: string;
  display_name: string;
  asset_type: string;
  aliases?: string[];
  metric_count?: number;
};

type AssetRegistrationStepProps = {
  platformType: PlatformType | null;
  integrationPreset?: "reneryo" | "mock" | null;
  onComplete: () => void;
  onSkip: () => void;
};

const ASSET_TYPES: RegistrationRow["assetType"][] = [
  "line",
  "machine",
  "sensor",
];
const LINE_ASSET_ID_PATTERN = /^line[-_ ]?\d+$/i;
const NATIVE_SEU_ENERGY_BINDINGS: NativeMetricBindings = {
  energy_total: {
    strategy: "asset_consumption_total",
    unit: "kWh",
    trend_supported: false,
    compare_supported: false,
    default_period_mode: "aggregate_total",
    aggregate_start_iso: "2021-02-01T00:00:00.000Z",
  },
};

function createRowId(seed?: string): string {
  const base = seed ? seed.replace(/[^a-zA-Z0-9_-]/g, "") : "asset";
  return `${base}-${Math.random().toString(36).slice(2, 10)}`;
}

function toDisplayName(assetId: string, explicitName: unknown): string {
  const trimmed = typeof explicitName === "string" ? explicitName.trim() : "";
  if (trimmed) {
    return trimmed;
  }
  return assetId
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function inferAssetType(
  assetId: string,
  explicitType: unknown,
): RegistrationRow["assetType"] {
  const normalizedType =
    typeof explicitType === "string" ? explicitType.toLowerCase() : "";
  if (normalizedType === "line" || normalizedType === "sensor") {
    return normalizedType;
  }
  if (LINE_ASSET_ID_PATTERN.test(assetId)) {
    return "line";
  }
  return "machine";
}

function toRegistrationRows(
  mappings: Record<string, AssetMappingItem>,
): RegistrationRow[] {
  const rows = Object.entries(mappings).map(([assetId, item]) => {
    const mappingSource: RegistrationRow["mappingSource"] =
      item.mapping_source === "generator" || item.mapping_source === "live_discovery"
        ? item.mapping_source
        : "manual";
    const capabilityMode: RegistrationRow["capabilityMode"] =
      item.capability_mode === "energy_only" ? "energy_only" : "full_kpi";

    return {
      rowId: createRowId(assetId),
      assetId,
      displayName: toDisplayName(assetId, item.display_name),
      assetType: inferAssetType(assetId, item.asset_type),
      aliases: aliasesToCsv(item.aliases),
      mappingSource,
      capabilityMode,
      nativeMetricBindings:
        item.native_metric_bindings && typeof item.native_metric_bindings === "object"
          ? (item.native_metric_bindings as NativeMetricBindings)
          : {},
      isExisting: true,
      existingAssetId: assetId,
    };
  });
  return rows.length > 0
    ? rows
    : [
        {
          rowId: createRowId(),
          assetId: "",
          displayName: "",
          assetType: "machine",
          aliases: "",
          mappingSource: "manual",
          capabilityMode: "full_kpi",
          nativeMetricBindings: {},
          isExisting: false,
          existingAssetId: null,
        },
      ];
}

function sanitizeAliasList(aliases: string[]): string[] {
  const deduped = new Set<string>();
  for (const rawAlias of aliases) {
    const alias = rawAlias.trim();
    if (!alias || alias.length > 32) {
      continue;
    }
    deduped.add(alias);
    if (deduped.size >= 5) {
      break;
    }
  }
  return Array.from(deduped);
}

function normalizeSuggestedAsset(
  asset: SuggestionInput,
  source: "live" | "generator",
): SuggestedAsset {
  const assetId = asset.asset_id.trim();
  const rawAliases =
    "aliases" in asset && Array.isArray(asset.aliases)
      ? asset.aliases.map((item) => String(item))
      : [];
  const aliases = sanitizeAliasList(rawAliases);

  return {
    asset_id: assetId,
    display_name: asset.display_name.trim() || assetId,
    asset_type: inferAssetType(assetId, asset.asset_type),
    aliases,
    metric_count:
      source === "generator" && typeof asset.metric_count === "number"
        ? asset.metric_count
        : undefined,
    source,
  };
}

function hasMetricResources(mapping: AssetMappingItem | undefined): boolean {
  if (!mapping || typeof mapping !== "object") {
    return false;
  }
  const resources = mapping.metric_resources;
  if (!resources || typeof resources !== "object") {
    return false;
  }
  return Object.values(resources).some((value) => String(value).trim().length > 0);
}

export default function AssetRegistrationStep({
  platformType,
  integrationPreset = null,
  onComplete,
  onSkip,
}: AssetRegistrationStepProps) {
  const shouldAttemptDiscovery =
    platformType !== "unconfigured" && integrationPreset === "reneryo";
  const shouldLoadGeneratorPreview = integrationPreset === "reneryo";
  const [rows, setRows] = useState<RegistrationRow[]>([]);
  const [storedMappings, setStoredMappings] = useState<
    Record<string, AssetMappingItem>
  >({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [discoveryLoading, setDiscoveryLoading] = useState(false);
  const [discoveryError, setDiscoveryError] = useState("");
  const [liveSuggestedAssets, setLiveSuggestedAssets] = useState<SuggestedAsset[]>([]);
  const [generatorLoading, setGeneratorLoading] = useState(false);
  const [generatorError, setGeneratorError] = useState("");
  const [generatorAssets, setGeneratorAssets] = useState<SuggestedAsset[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const mappingsResponse = await getConfiguredAssets();
      const existingMappings = mappingsResponse.asset_mappings;
      const registrationRows = toRegistrationRows(existingMappings);
      setStoredMappings(existingMappings);
      setRows(registrationRows);

      if (shouldLoadGeneratorPreview) {
        setGeneratorLoading(true);
        setGeneratorError("");
        try {
          const preview = await getGeneratorAssetPreview();
          if (preview.available) {
            const nextGeneratorAssets = (preview.assets ?? [])
              .filter((asset) => typeof asset.asset_id === "string" && asset.asset_id.trim())
              .map((asset) => normalizeSuggestedAsset(asset, "generator"));
            setGeneratorAssets(nextGeneratorAssets);
          } else {
            setGeneratorAssets([]);
            if (preview.error) {
              setGeneratorError(preview.error);
            }
          }
        } catch (generatorErr: unknown) {
          setGeneratorError(toFriendlyErrorMessage(generatorErr));
          setGeneratorAssets([]);
        } finally {
          setGeneratorLoading(false);
        }
      } else {
        setGeneratorLoading(false);
        setGeneratorError("");
        setGeneratorAssets([]);
      }

      if (shouldAttemptDiscovery) {
        setDiscoveryLoading(true);
        setDiscoveryError("");
        try {
          const discovery = await getAssetDiscovery();
          const nextSuggestions = (discovery.assets ?? [])
            .filter((asset) => typeof asset.asset_id === "string" && asset.asset_id.trim())
            .map((asset) => normalizeSuggestedAsset(asset, "live"));
          setLiveSuggestedAssets(nextSuggestions);
          setRows((prev) =>
            prev.map((row) => {
              const rowAssetId = (row.existingAssetId ?? row.assetId).trim().toLowerCase();
              if (!rowAssetId) {
                return row;
              }
              const isLiveAsset = nextSuggestions.some(
                (asset) => asset.asset_id.toLowerCase() === rowAssetId,
              );
              if (!isLiveAsset) {
                return row;
              }

              const currentMapping = existingMappings[row.existingAssetId ?? row.assetId];
              if (hasMetricResources(currentMapping)) {
                return row;
              }

              return {
                ...row,
                mappingSource: "live_discovery",
                capabilityMode: "energy_only",
                nativeMetricBindings:
                  Object.keys(row.nativeMetricBindings ?? {}).length > 0
                    ? row.nativeMetricBindings
                    : { ...NATIVE_SEU_ENERGY_BINDINGS },
              };
            }),
          );
          if (discovery.discovery_error) {
            setDiscoveryError(discovery.discovery_error);
          }
        } catch (discoverErr: unknown) {
          setDiscoveryError(toFriendlyErrorMessage(discoverErr));
          setLiveSuggestedAssets([]);
        } finally {
          setDiscoveryLoading(false);
        }
      } else {
        setDiscoveryLoading(false);
        setDiscoveryError("");
        setLiveSuggestedAssets([]);
      }
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [shouldAttemptDiscovery, shouldLoadGeneratorPreview]);

  useEffect(() => {
    void load();
  }, [load]);

  const updateRow = useCallback(
    <K extends keyof RegistrationRow>(
      index: number,
      key: K,
      value: RegistrationRow[K],
    ) => {
      setRows((prev) =>
        prev.map((row, rowIndex) =>
          rowIndex === index ? { ...row, [key]: value } : row,
        ),
      );
    },
    [],
  );

  const addRow = useCallback(() => {
    setRows((prev) => [
      ...prev,
      {
        rowId: createRowId(),
        assetId: "",
        displayName: "",
        assetType: "machine",
        aliases: "",
        mappingSource: "manual",
        capabilityMode: "full_kpi",
        nativeMetricBindings: {},
        isExisting: false,
        existingAssetId: null,
      },
    ]);
  }, []);

  const deleteRow = useCallback((index: number) => {
    setRows((prev) => {
      const next = prev.filter((_, rowIndex) => rowIndex !== index);
      return next.length > 0
        ? next
        : [
            {
              rowId: createRowId(),
              assetId: "",
              displayName: "",
              assetType: "machine",
              aliases: "",
              mappingSource: "manual",
              capabilityMode: "full_kpi",
              nativeMetricBindings: {},
              isExisting: false,
              existingAssetId: null,
            },
          ];
    });
  }, []);

  const validationError = useMemo(() => {
    const seen = new Set<string>();
    for (const row of rows) {
      const resolvedId = row.assetId.trim() || toAssetId(row.displayName);
      const hasAnyValue =
        row.assetId.trim() || row.displayName.trim() || row.aliases.trim();
      if (!resolvedId && hasAnyValue) {
        return "Each asset requires an Asset ID or a Display Name.";
      }
      if (!resolvedId) {
        continue;
      }
      if (!/^[A-Za-z0-9-]+$/.test(resolvedId)) {
        return `Asset ID '${resolvedId}' can only contain letters, numbers, and hyphens.`;
      }
      if (seen.has(resolvedId.toLowerCase())) {
        return `Asset ID '${resolvedId}' is duplicated.`;
      }
      seen.add(resolvedId.toLowerCase());
      if (!row.displayName.trim()) {
        return `Display Name is required for asset '${resolvedId}'.`;
      }
      const aliases = csvToAliases(row.aliases);
      if (aliases.length > 5) {
        return `Asset '${resolvedId}' has more than 5 aliases.`;
      }
      if (aliases.some((alias) => alias.length > 32)) {
        return `Asset '${resolvedId}' has an alias longer than 32 characters.`;
      }
    }
    return "";
  }, [rows]);

  const saveAndContinue = useCallback(async () => {
    if (validationError) {
      setError(validationError);
      return;
    }
    setSaving(true);
    setError("");
    try {
      const payload = rows.reduce<Record<string, AssetMappingItem>>(
        (acc, row) => {
          const resolvedId = row.assetId.trim() || toAssetId(row.displayName);
          const targetId = row.existingAssetId ?? resolvedId;
          if (!targetId) {
            return acc;
          }
          const previous = storedMappings[targetId] ?? {};
          acc[targetId] = {
            ...previous,
            display_name: row.displayName.trim() || targetId,
            asset_type: row.assetType,
            aliases: csvToAliases(row.aliases),
            mapping_source: row.mappingSource,
            capability_mode: row.capabilityMode,
            native_metric_bindings:
              row.capabilityMode === "energy_only" ? row.nativeMetricBindings : {},
          };
          return acc;
        },
        {},
      );
      const response = await saveConfiguredAssets(payload);
      setStoredMappings(response.asset_mappings);
      onComplete();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [onComplete, rows, storedMappings, validationError]);

  const importAssetCandidate = useCallback((candidate: SuggestedAsset) => {
    setRows((prev) => {
      const candidateId = candidate.asset_id.toLowerCase();
      const existingIndex = prev.findIndex(
        (row) => (row.existingAssetId ?? row.assetId).trim().toLowerCase() === candidateId,
      );
      if (existingIndex >= 0) {
        if (candidate.source !== "live") {
          return prev;
        }

        const current = prev[existingIndex];
        const currentMapping = storedMappings[current.existingAssetId ?? current.assetId];
        if (hasMetricResources(currentMapping)) {
          return prev;
        }

        const next = [...prev];
        next[existingIndex] = {
          ...current,
          displayName: current.displayName.trim() ? current.displayName : candidate.display_name,
          assetType: current.assetType || candidate.asset_type,
          mappingSource: "live_discovery",
          capabilityMode: "energy_only",
          nativeMetricBindings:
            Object.keys(current.nativeMetricBindings ?? {}).length > 0
              ? current.nativeMetricBindings
              : { ...NATIVE_SEU_ENERGY_BINDINGS },
        };
        return next;
      }

      const draftRows = [...prev];
      const onlyBlankDraft =
        draftRows.length === 1 &&
        !draftRows[0].assetId.trim() &&
        !draftRows[0].displayName.trim() &&
        !draftRows[0].aliases.trim();
      const nextRows = onlyBlankDraft ? [] : draftRows;
      nextRows.push({
        rowId: createRowId(candidate.asset_id),
        assetId: candidate.asset_id,
        displayName: candidate.display_name,
        assetType: candidate.asset_type,
        aliases: aliasesToCsv(sanitizeAliasList(candidate.aliases)),
        mappingSource: candidate.source === "generator" ? "generator" : "live_discovery",
        capabilityMode: candidate.source === "generator" ? "full_kpi" : "energy_only",
        nativeMetricBindings:
          candidate.source === "generator" ? {} : { ...NATIVE_SEU_ENERGY_BINDINGS },
        isExisting: false,
        existingAssetId: null,
      });
      return nextRows;
    });
  }, [storedMappings]);

  const importLiveSuggestedAsset = useCallback(
    (assetId: string) => {
      const candidate = liveSuggestedAssets.find((asset) => asset.asset_id === assetId);
      if (!candidate) {
        return;
      }
      importAssetCandidate(candidate);
    },
    [importAssetCandidate, liveSuggestedAssets],
  );

  const importAllLiveSuggestedAssets = useCallback(() => {
    for (const asset of liveSuggestedAssets) {
      importAssetCandidate(asset);
    }
  }, [importAssetCandidate, liveSuggestedAssets]);

  const importGeneratorAsset = useCallback(
    (assetId: string) => {
      const candidate = generatorAssets.find((asset) => asset.asset_id === assetId);
      if (!candidate) {
        return;
      }
      importAssetCandidate(candidate);
    },
    [generatorAssets, importAssetCandidate],
  );

  const importAllGeneratorAssets = useCallback(() => {
    for (const asset of generatorAssets) {
      importAssetCandidate(asset);
    }
  }, [generatorAssets, importAssetCandidate]);

  const subtitle =
    platformType === "unconfigured"
      ? "Define your factory vocabulary even in demo mode."
      : "Define the assets users will reference in voice commands and KPI queries.";

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 2 of 5
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Asset Registration
          </h2>
          <Tooltip
            content="Register factory assets as voice-addressable names before linking them to platform resources."
            ariaLabel="Why asset registration is needed"
          />
        </div>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          {subtitle}
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
            Loading assets...
          </div>
        ) : (
          <div className="space-y-3">
            <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
              Aliases improve voice matching, for example: "line one, first line, l1".
            </p>
            <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
              Existing Asset IDs are immutable. Add a new row to register a new asset ID.
            </p>

            {shouldLoadGeneratorPreview && (
              <div className="rounded-xl border border-slate-300 bg-white/90 p-3 dark:border-slate-600 dark:bg-slate-800/80">
                <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                  KPI-ready Generator Assets
                </p>
                <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Preview assets found in mapping_output.json. These are AVAROS query assets like Line-1 / Line-2 / Line-3.
                </p>
                {generatorLoading && (
                  <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
                    Loading generator asset preview...
                  </p>
                )}
                {!generatorLoading && generatorError && (
                  <p className="m-0 mt-2 text-xs text-amber-700 dark:text-amber-300">
                    Generator preview warning: {generatorError}
                  </p>
                )}
                {!generatorLoading && generatorAssets.length === 0 && !generatorError && (
                  <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
                    No generator-backed assets detected yet. You can still add assets manually.
                  </p>
                )}
                {!generatorLoading && generatorAssets.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                        onClick={importAllGeneratorAssets}
                      >
                        Import All ({generatorAssets.length})
                      </button>
                    </div>
                    {generatorAssets.slice(0, 8).map((asset) => (
                      <div
                        key={asset.asset_id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700"
                      >
                        <div>
                          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {asset.display_name}
                          </p>
                          <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                            {asset.asset_id} · {asset.asset_type} · {asset.metric_count ?? 0}/19 metrics
                          </p>
                          <p className="m-0 mt-1 text-xs text-emerald-700 dark:text-emerald-300">
                            Full KPI coverage
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                          onClick={() => importGeneratorAsset(asset.asset_id)}
                        >
                          Add
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {shouldAttemptDiscovery && (
              <div className="rounded-xl border border-slate-300 bg-white/90 p-3 dark:border-slate-600 dark:bg-slate-800/80">
                <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-slate-500 dark:text-slate-400">
                  Live RENERYO Resources
                </p>
                <p className="m-0 mt-1 text-xs text-slate-500 dark:text-slate-400">
                  Import assets discovered from the active API connection (SEU list).
                </p>
                {discoveryLoading && (
                  <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
                    Discovering assets from live API...
                  </p>
                )}
                {!discoveryLoading && discoveryError && (
                  <p className="m-0 mt-2 text-xs text-amber-700 dark:text-amber-300">
                    Discovery warning: {discoveryError}
                  </p>
                )}
                {!discoveryLoading && liveSuggestedAssets.length === 0 && !discoveryError && (
                  <p className="m-0 mt-2 text-xs text-slate-500 dark:text-slate-400">
                    No live assets discovered yet. You can continue with manual registration.
                  </p>
                )}
                {!discoveryLoading && liveSuggestedAssets.length > 0 && (
                  <div className="mt-2 space-y-2">
                    <div className="flex flex-wrap gap-2">
                      <button
                        type="button"
                        className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                        onClick={importAllLiveSuggestedAssets}
                      >
                        Import All ({liveSuggestedAssets.length})
                      </button>
                    </div>
                    {liveSuggestedAssets.slice(0, 8).map((asset) => (
                      <div
                        key={asset.asset_id}
                        className="flex items-center justify-between rounded-lg border border-slate-200 px-3 py-2 dark:border-slate-700"
                      >
                        <div>
                          <p className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                            {asset.display_name}
                          </p>
                          <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
                            {asset.asset_id} · {asset.asset_type}
                          </p>
                          <p className="m-0 mt-1 text-xs text-amber-700 dark:text-amber-300">
                            Energy-only capability
                          </p>
                        </div>
                        <button
                          type="button"
                          className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
                          onClick={() => importLiveSuggestedAsset(asset.asset_id)}
                        >
                          Add
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {rows.map((row, index) => (
              <div
                key={row.rowId}
                className="grid gap-2 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800 md:grid-cols-5"
              >
                <input
                  type="text"
                  value={row.assetId}
                  placeholder="asset-id"
                  disabled={row.isExisting}
                  title={row.isExisting ? "Asset ID is immutable after creation." : undefined}
                  onChange={(event) =>
                    updateRow(index, "assetId", event.target.value)
                  }
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm disabled:cursor-not-allowed disabled:opacity-60 dark:border-slate-600 dark:bg-slate-900"
                />
                <input
                  type="text"
                  value={row.displayName}
                  placeholder="Display Name"
                  onChange={(event) =>
                    updateRow(index, "displayName", event.target.value)
                  }
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                />
                <select
                  value={row.assetType}
                  onChange={(event) =>
                    updateRow(
                      index,
                      "assetType",
                      event.target.value as RegistrationRow["assetType"],
                    )
                  }
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900"
                >
                  {ASSET_TYPES.map((assetType) => (
                    <option key={assetType} value={assetType}>
                      {assetType}
                    </option>
                  ))}
                </select>
                <input
                  type="text"
                  value={row.aliases}
                  placeholder="Aliases (comma-separated)"
                  onChange={(event) =>
                    updateRow(index, "aliases", event.target.value)
                  }
                  className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm dark:border-slate-600 dark:bg-slate-900 md:col-span-2"
                />
                <div className="md:col-span-5">
                  {integrationPreset === "reneryo" && (
                    <p className="m-0 mb-2 text-xs text-slate-500 dark:text-slate-400">
                      Mode: {row.capabilityMode === "energy_only" ? "Energy only (compatibility)" : "Full KPI"}
                    </p>
                  )}
                  <button
                    type="button"
                    className="rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold dark:border-slate-600"
                    onClick={() => deleteRow(index)}
                  >
                    Delete
                  </button>
                </div>
              </div>
            ))}

            <button
              type="button"
              className="btn-brand-subtle rounded-lg px-3 py-2 text-sm font-semibold"
              onClick={addRow}
            >
              Add Asset
            </button>
          </div>
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
            disabled={saving || loading}
          >
            {saving ? "Saving..." : "Save & Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
