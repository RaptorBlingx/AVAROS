import type { CanonicalMetricName } from "../../api/types";

/* ------------------------------------------------------------------ */
/*  Preset JSON shape (matches public/wizard-preset-reneryo.json)      */
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

export async function loadWizardPreset(profileName?: string): Promise<WizardPreset> {
  const key = profileName ?? "reneryo";
  if (_cache[key]) {
    return _cache[key];
  }
  const response = await fetch(`/wizard-preset-${key}.json`);
  if (!response.ok) {
    throw new Error(`No preset file found for profile "${key}" (HTTP ${response.status})`);
  }
  const data = (await response.json()) as WizardPreset;
  _cache[key] = data;
  return data;
}

export async function hasWizardPreset(profileName?: string): Promise<boolean> {
  const key = profileName ?? "reneryo";
  if (_cache[key]) {
    return true;
  }
  try {
    const response = await fetch(`/wizard-preset-${key}.json`, { method: "HEAD" });
    return response.ok;
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
