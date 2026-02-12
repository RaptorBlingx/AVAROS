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
