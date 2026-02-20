import { useCallback, useEffect, useMemo, useState } from "react";

import {
  discoverAssets,
  getAssetMappings,
  setAssetMappings,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  AssetDiscoveryResponse,
  AssetMappingItem,
  MetricResourceOption,
} from "../../api/types";
import Tooltip from "../common/Tooltip";

type AssetMappingStepProps = {
  onComplete: () => void;
  onSkip: () => void;
};

type AssetRow = {
  assetKey: string;
  seuId: string;
  oeeResourceId: string;
  scrapResourceId: string;
};

const DEFAULT_ASSET_KEYS = ["Line-1", "Line-2"];

function toRows(mappings: Record<string, AssetMappingItem>): AssetRow[] {
  const rows = Object.entries(mappings).map(([assetKey, value]) => ({
    assetKey,
    seuId: value.seu_id ?? "",
    oeeResourceId: value.metric_resources?.oee ?? "",
    scrapResourceId: value.metric_resources?.scrap_rate ?? "",
  }));
  if (rows.length > 0) {
    return rows;
  }
  return DEFAULT_ASSET_KEYS.map((assetKey) => ({
    assetKey,
    seuId: "",
    oeeResourceId: "",
    scrapResourceId: "",
  }));
}

function toPayload(rows: AssetRow[]): Record<string, AssetMappingItem> {
  return rows.reduce<Record<string, AssetMappingItem>>((acc, row) => {
    const key = row.assetKey.trim();
    if (!key) {
      return acc;
    }
    acc[key] = {
      seu_id: row.seuId.trim(),
      metric_resources: {
        oee: row.oeeResourceId.trim(),
        scrap_rate: row.scrapResourceId.trim(),
      },
    };
    return acc;
  }, {});
}

function mapResources(
  response: AssetDiscoveryResponse | null,
  key: "oee" | "scrap_rate",
): MetricResourceOption[] {
  if (!response) {
    return [];
  }
  return response.resources?.[key] ?? [];
}

export default function AssetMappingStep({
  onComplete,
  onSkip,
}: AssetMappingStepProps) {
  const [rows, setRows] = useState<AssetRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [discovering, setDiscovering] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");
  const [discovery, setDiscovery] = useState<AssetDiscoveryResponse | null>(
    null,
  );

  const loadMappings = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const current = await getAssetMappings();
      setRows(toRows(current.asset_mappings));
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadMappings();
  }, [loadMappings]);

  const handleDiscover = useCallback(async () => {
    setDiscovering(true);
    setError("");
    try {
      const data = await discoverAssets();
      setDiscovery(data);
      if (Object.keys(data.existing_mappings).length > 0) {
        setRows(toRows(data.existing_mappings));
      } else if (data.seus.length > 0 && rows.every((row) => !row.seuId)) {
        const next = [...rows];
        for (let i = 0; i < next.length && i < data.seus.length; i += 1) {
          next[i] = { ...next[i], seuId: data.seus[i].id };
        }
        setRows(next);
      }
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setDiscovering(false);
    }
  }, [rows]);

  const handleRowChange = useCallback(
    <K extends keyof AssetRow>(index: number, field: K, value: AssetRow[K]) => {
      setRows((prev) =>
        prev.map((row, rowIndex) =>
          rowIndex === index ? { ...row, [field]: value } : row,
        ),
      );
    },
    [],
  );

  const handleSave = useCallback(async () => {
    setSaving(true);
    setError("");
    try {
      await setAssetMappings(toPayload(rows));
      onComplete();
    } catch (err: unknown) {
      setError(toFriendlyErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }, [onComplete, rows]);

  const seuOptions = useMemo(() => discovery?.seus ?? [], [discovery]);
  const oeeOptions = useMemo(() => mapResources(discovery, "oee"), [discovery]);
  const scrapOptions = useMemo(
    () => mapResources(discovery, "scrap_rate"),
    [discovery],
  );

  return (
    <section className="space-y-4">
      <header className="brand-hero rounded-2xl p-6 backdrop-blur-sm">
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-sky-700 dark:text-sky-300">
          Step 4 of 7
        </p>
        <div className="mt-2 inline-flex items-center gap-2">
          <h2 className="m-0 text-2xl font-semibold text-slate-900 dark:text-slate-100">
            Asset Mapping
          </h2>
          <Tooltip
            content="Map voice assets (Line-1, Line-2) to RENERYO SEU and metric resource IDs."
            ariaLabel="Why asset mapping is needed"
          />
        </div>
      </header>

      <div className="brand-hero rounded-2xl p-6 backdrop-blur-sm space-y-4">
        {error && (
          <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-900 dark:border-red-500/40 dark:bg-red-900/40 dark:text-red-200">
            {error}
          </div>
        )}

        <div className="flex items-center justify-between gap-3">
          <p className="m-0 text-sm text-slate-600 dark:text-slate-300">
            Discover SEUs and metric resources from RENERYO, then map each
            asset.
          </p>
          <button
            type="button"
            onClick={() => void handleDiscover()}
            disabled={discovering || loading}
            className="btn-brand-subtle rounded-lg px-4 py-2 text-sm font-semibold"
          >
            {discovering ? "Discovering..." : "Discover from RENERYO"}
          </button>
        </div>

        {loading ? (
          <div className="rounded-lg border border-slate-300 bg-white px-4 py-3 text-sm text-slate-700 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200">
            Loading current mappings...
          </div>
        ) : (
          <div className="space-y-3">
            {rows.map((row, index) => (
              <div
                key={`${row.assetKey}-${index}`}
                className="grid gap-3 rounded-xl border border-slate-300 bg-white p-3 dark:border-slate-600 dark:bg-slate-800 md:grid-cols-4"
              >
                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    Asset Key
                  </span>
                  <input
                    type="text"
                    value={row.assetKey}
                    onChange={(event) =>
                      handleRowChange(index, "assetKey", event.target.value)
                    }
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                  />
                </label>

                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    SEU ID
                  </span>
                  <select
                    value={row.seuId}
                    onChange={(event) =>
                      handleRowChange(index, "seuId", event.target.value)
                    }
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="">Select SEU</option>
                    {seuOptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.id})
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    OEE Resource
                  </span>
                  <select
                    value={row.oeeResourceId}
                    onChange={(event) =>
                      handleRowChange(
                        index,
                        "oeeResourceId",
                        event.target.value,
                      )
                    }
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="">Optional</option>
                    {oeeOptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.id})
                      </option>
                    ))}
                  </select>
                </label>

                <label className="block">
                  <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">
                    Scrap Resource
                  </span>
                  <select
                    value={row.scrapResourceId}
                    onChange={(event) =>
                      handleRowChange(
                        index,
                        "scrapResourceId",
                        event.target.value,
                      )
                    }
                    className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                  >
                    <option value="">Optional</option>
                    {scrapOptions.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name} ({item.id})
                      </option>
                    ))}
                  </select>
                </label>
              </div>
            ))}
          </div>
        )}

        <div className="mt-4 flex flex-wrap gap-3">
          <button
            type="button"
            className="btn-brand-subtle inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold"
            onClick={onSkip}
          >
            Skip
          </button>
          <button
            type="button"
            className="btn-brand-primary inline-flex items-center rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            onClick={() => void handleSave()}
            disabled={saving || loading}
          >
            {saving ? "Saving..." : "Save Mapping & Continue"}
          </button>
        </div>
      </div>
    </section>
  );
}
