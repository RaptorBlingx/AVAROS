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
