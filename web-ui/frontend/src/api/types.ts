export type HealthResponse = {
  status: string;
  version: string;
};

export type SystemStatusResponse = {
  configured: boolean;
  active_adapter: string;
  platform_type: string;
  loaded_intents: number;
  database_connected: boolean;
  version: string;
};

export type PlatformType = "mock" | "reneryo" | "custom_rest";

export type PlatformConfigRequest = {
  platform_type: PlatformType;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, string>;
};

export type PlatformConfigResponse = {
  platform_type: PlatformType;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, string>;
};

export type PlatformResetResponse = {
  status: "reset";
  platform_type: PlatformType;
};

export type ConnectionTestResponse = {
  success: boolean;
  message: string;
  latency_ms?: number;
  adapter_name?: string;
  resources_discovered?: string[];
  error_code?: string;
  error_details?: string;
};

export type CanonicalMetricName =
  | "energy_per_unit"
  | "energy_total"
  | "peak_demand"
  | "peak_tariff_exposure"
  | "scrap_rate"
  | "rework_rate"
  | "material_efficiency"
  | "recycled_content"
  | "supplier_lead_time"
  | "supplier_defect_rate"
  | "supplier_on_time"
  | "supplier_co2_per_kg"
  | "oee"
  | "throughput"
  | "cycle_time"
  | "changeover_time"
  | "co2_per_unit"
  | "co2_total"
  | "co2_per_batch";

export type MetricMapping = {
  canonical_metric: CanonicalMetricName;
  endpoint: string;
  json_path: string;
  unit: string;
  transform: string | null;
};

export type MetricMappingRequest = MetricMapping;

export type MetricMappingTestRequest = {
  base_url: string;
  endpoint: string;
  json_path: string;
  auth_type: "bearer" | "cookie";
  auth_token: string;
};

export type MetricMappingTestResponse = {
  success: boolean;
  value: number | null;
  raw_response_preview: string;
  error: string | null;
};

export type NonMetricIntentName =
  | "control.device.turn_on"
  | "control.device.turn_off"
  | "status.system.show"
  | "status.profile.show"
  | "help.capabilities.list";

export type IntentBindingMethod = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export type IntentBinding = {
  intent_name: NonMetricIntentName;
  endpoint: string;
  method: IntentBindingMethod;
  json_path: string;
  success_path: string | null;
  transform: string | null;
};

export type IntentBindingRequest = IntentBinding;

export type IntentState = {
  intent_name: string;
  active: boolean;
  required_metrics: CanonicalMetricName[];
};

export type IntentListResponse = IntentState[];

export type KPIMetricName =
  | "energy_per_unit"
  | "material_efficiency"
  | "co2_total";

export type KPIProgressItem = {
  metric: KPIMetricName;
  site_id: string;
  baseline_value: number;
  current_value: number;
  target_percent: number;
  improvement_percent: number;
  target_met: boolean;
  unit: string;
  baseline_date: string;
  current_date: string;
  direction: "improving" | "worsening" | "stable" | string;
};

export type SiteProgressResponse = {
  site_id: string;
  baselines_count: number;
  targets_met: number;
  targets_total: number;
  progress: KPIProgressItem[];
};

export type BaselineResponse = {
  id: number;
  metric: KPIMetricName;
  site_id: string;
  baseline_value: number;
  unit: string;
  recorded_at: string;
  period_start: string;
  period_end: string;
  notes: string | null;
};

export type SnapshotResponse = {
  id: number;
  metric: KPIMetricName;
  site_id: string;
  value: number;
  unit: string;
  measured_at: string;
  period_start: string;
  period_end: string;
};

export type ProductionRecordRequest = {
  record_date: string;
  asset_id: string;
  production_count: number;
  good_count: number;
  material_consumed_kg: number;
  shift?: string;
  batch_id?: string;
  notes?: string;
};

export type ProductionRecordResponse = {
  id: number;
  record_date: string;
  asset_id: string;
  production_count: number;
  good_count: number;
  material_consumed_kg: number;
  shift: string;
  batch_id: string;
  notes: string;
  created_at: string | null;
};

export type ProductionRecordListResponse = {
  records: ProductionRecordResponse[];
  total: number;
};

export type CSVUploadResponse = {
  total_rows: number;
  valid_rows: number;
  inserted: number;
  errors: Array<{
    row: number;
    column: string;
    message: string;
  }>;
};

export type ProductionSummaryResponse = {
  asset_id: string;
  start_date: string;
  end_date: string;
  total_produced: number;
  total_good: number;
  total_material_kg: number;
  record_count: number;
  material_efficiency_pct: number;
};

export type EnergySource = "electricity" | "gas" | "water";

export type EmissionFactorRequest = {
  energy_source: EnergySource;
  factor: number;
  country: string;
  source: string;
  year: number;
};

export type EmissionFactorResponse = {
  energy_source: string;
  factor: number;
  country: string;
  source: string;
  year: number;
};

export type EmissionFactorListResponse = {
  factors: EmissionFactorResponse[];
};

export type EmissionFactorPresetResponse = {
  country: string;
  energy_source: string;
  factor: number;
  source: string;
  year: number;
};

export type VoiceConfigResponse = {
  hivemind_url: string;
  hivemind_name: string;
  hivemind_key: string;
  hivemind_secret: string;
  voice_enabled: boolean;
};

// ── Profile Types ──────────────────────────────────────

export type ProfileMetadata = {
  name: string;
  platform_type: string;
  is_builtin: boolean;
  is_active: boolean;
};

export type ProfileListResponse = {
  active_profile: string;
  profiles: ProfileMetadata[];
};

export type ProfileDetailResponse = {
  name: string;
  platform_type: string;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, string>;
  is_builtin: boolean;
  is_active: boolean;
};

export type CreateProfileRequest = {
  name: string;
  platform_type: string;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, string>;
};

export type UpdateProfileRequest = {
  platform_type: string;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, string>;
};

export type ActivateProfileResponse = {
  status: string;
  active_profile: string;
  adapter_type: string;
  message: string;
  voice_reloaded?: boolean;
};

export type DeleteProfileResponse = {
  status: string;
  deleted_profile: string;
  active_profile: string;
  message: string;
};

export type MetricResourceMap = Record<string, string>;

export type AssetMappingItem = {
  display_name?: string;
  asset_type?: "machine" | "line" | "sensor" | "seu";
  aliases?: string[];
  endpoint_template?: string;
  seu_id?: string;
  metric_resources?: MetricResourceMap;
  [key: string]: unknown;
};

export type AssetMappingsResponse = {
  asset_mappings: Record<string, AssetMappingItem>;
};

export type AssetRecord = {
  asset_id: string;
  display_name: string;
  asset_type: "machine" | "line" | "sensor" | "seu";
  aliases: string[];
  metadata?: Record<string, unknown>;
};

export type AssetDiscoveryResponse = {
  platform_type: PlatformType;
  supports_discovery: boolean;
  assets: AssetRecord[];
  existing_mappings: Record<string, AssetMappingItem>;
};

export type ProfileConfig = {
  platform_type: string;
  api_url: string;
  api_key: string;
  extra_settings: Record<string, any>;
};
