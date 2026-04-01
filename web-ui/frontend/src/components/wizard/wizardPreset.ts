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

let _cache: WizardPreset | null = null;

export async function loadWizardPreset(): Promise<WizardPreset> {
  if (_cache) {
    return _cache;
  }
  const response = await fetch("/wizard-preset-reneryo.json");
  if (!response.ok) {
    throw new Error(`Failed to load wizard preset (HTTP ${response.status})`);
  }
  const data = (await response.json()) as WizardPreset;
  _cache = data;
  return data;
}

export function clearPresetCache(): void {
  _cache = null;
}
