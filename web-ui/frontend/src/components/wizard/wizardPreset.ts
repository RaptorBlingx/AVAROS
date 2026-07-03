import type { CanonicalMetricName } from "../../api/types";

/* ------------------------------------------------------------------ */
/*  Preset JSON shape (matches public/wizard-preset-<profile>.json)    */
/* ------------------------------------------------------------------ */

export type PresetAsset = {
  asset_id: string;
  display_name: string;
  asset_type: "line" | "machine" | "sensor";
  aliases: string;
};

export type PresetMetricMapping = {
  canonical_metric: CanonicalMetricName;
  unit: string;
  endpoint?: string;
  json_path?: string;
};

export type PresetMetrics = {
  endpoint: string;
  json_path: string;
  mappings: PresetMetricMapping[];
};

export type WizardPreset = {
  _description?: string;
  _updated?: string;
  platform: {
    api_url: string;
    auth_type: string;
    credential: string;
  };
  assets: PresetAsset[];
  metrics: PresetMetrics;
  linking: Record<string, Record<string, string>>;
};

/* ------------------------------------------------------------------ */
/*  Loader (fetches from public/ at runtime — fully editable)          */
/* ------------------------------------------------------------------ */

const _cache: Record<string, WizardPreset> = {};

function presetUrl(key: string): string {
  return `/wizard-preset-${encodeURIComponent(key)}.json`;
}

function isWizardPreset(value: unknown): value is WizardPreset {
  if (!value || typeof value !== "object") {
    return false;
  }
  const candidate = value as Partial<WizardPreset>;
  return (
    Array.isArray(candidate.assets) &&
    Boolean(candidate.metrics) &&
    typeof candidate.metrics === "object" &&
    Array.isArray(candidate.metrics.mappings) &&
    Boolean(candidate.linking) &&
    typeof candidate.linking === "object"
  );
}

export async function loadWizardPreset(profileName?: string): Promise<WizardPreset> {
  const key = profileName ?? "demo";
  if (_cache[key]) {
    return _cache[key];
  }
  const response = await fetch(presetUrl(key), {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`No preset file found for profile "${key}" (HTTP ${response.status})`);
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (!contentType.includes("application/json")) {
    throw new Error(
      `No bundled preset is available for profile "${key}". Register the assets manually or provide a wizard-preset-${key}.json file.`,
    );
  }

  let data: unknown;
  try {
    data = await response.json();
  } catch {
    throw new Error(`The preset file for profile "${key}" is not valid JSON.`);
  }
  if (!isWizardPreset(data)) {
    throw new Error(`The preset file for profile "${key}" has an invalid structure.`);
  }

  _cache[key] = data;
  return data;
}

export async function hasWizardPreset(profileName?: string): Promise<boolean> {
  const key = profileName ?? "demo";
  if (_cache[key]) {
    return true;
  }
  try {
    await loadWizardPreset(key);
    return true;
  } catch {
    return false;
  }
}

export function clearPresetCache(profileName?: string): void {
  if (profileName) {
    delete _cache[profileName];
  } else {
    for (const k of Object.keys(_cache)) {
      delete _cache[k];
    }
  }
}
