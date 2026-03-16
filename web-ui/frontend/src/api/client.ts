import type {
  ActivateProfileResponse,
  AssetLinkingSummaryResponse,
  AssetDiscoveryResponse,
  AssetMappingItem,
  AssetRecord,
  AssetMappingsResponse,
  BaselineResponse,
  CSVUploadResponse,
  CanonicalMetricName,
  ConnectionTestResponse,
  CreateProfileRequest,
  DeleteProfileResponse,
  EmissionFactorListResponse,
  EmissionFactorPresetResponse,
  EmissionFactorRequest,
  EmissionFactorResponse,
  GeneratorMappingResponse,
  HealthResponse,
  IntentBinding,
  IntentBindingRequest,
  IntentListResponse,
  IntentState,
  MetricMapping,
  MetricMappingRequest,
  MetricMappingTestRequest,
  MetricMappingTestResponse,
  PlatformConfigRequest,
  PlatformConfigResponse,
  PlatformResetResponse,
  ProductionRecordListResponse,
  ProductionRecordRequest,
  ProductionRecordResponse,
  ProductionSummaryResponse,
  ProfileDetailResponse,
  ProfileListResponse,
  SiteProgressResponse,
  SnapshotResponse,
  SystemStatusResponse,
  UpdateProfileRequest,
  VoiceConfigResponse,
} from "./types";

const API_BASE_URL = "";
const API_KEY_STORAGE_KEY = "avaros_api_key";
export const DEFAULT_SITE_ID = "pilot-1";
const CANONICAL_METRIC_NAMES: CanonicalMetricName[] = [
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
];

/**
 * Get the stored API key from localStorage.
 */
export function getStoredApiKey(): string {
  return localStorage.getItem(API_KEY_STORAGE_KEY) ?? "";
}

/**
 * Save an API key to localStorage.
 */
export function setStoredApiKey(key: string): void {
  localStorage.setItem(API_KEY_STORAGE_KEY, key);
}

/**
 * Remove the stored API key (logout).
 */
export function clearStoredApiKey(): void {
  localStorage.removeItem(API_KEY_STORAGE_KEY);
}

export class ApiError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "ApiError";
    this.status = status;
  }
}

export function toFriendlyErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 0) {
      return "Connection lost — check if AVAROS is running.";
    }
    if (!error.message || error.message === "Request failed") {
      return "Something went wrong while talking to AVAROS.";
    }
    return error.message;
  }
  if (error instanceof Error) {
    return error.message || "Something went wrong while talking to AVAROS.";
  }
  return "Something went wrong while talking to AVAROS.";
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "DELETE";
  body?: unknown;
};

async function parseErrorMessage(response: Response): Promise<string> {
  let message = "Request failed";
  try {
    const data = (await response.json()) as { detail?: unknown };
    if (typeof data.detail === "string") {
      return data.detail;
    }
    if (Array.isArray(data.detail) && data.detail.length > 0) {
      const first = data.detail[0] as { msg?: string };
      return first.msg ?? message;
    }
  } catch {
    return message;
  }
  return message;
}

async function request<T>(
  path: string,
  options: RequestOptions = {},
): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
  };

  const apiKey = getStoredApiKey();
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      method: options.method ?? "GET",
      headers,
      body: options.body ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError("Cannot connect to server", 0);
  }

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }
  if (response.status === 204) {
    return undefined as T;
  }
  return (await response.json()) as T;
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("/health");
}

export function getStatus(): Promise<SystemStatusResponse> {
  return request<SystemStatusResponse>("/api/v1/status");
}

export function createPlatformConfig(
  payload: PlatformConfigRequest,
): Promise<PlatformConfigResponse> {
  return request<PlatformConfigResponse>("/api/v1/config/platform", {
    method: "POST",
    body: payload,
  });
}

export function getPlatformConfig(): Promise<PlatformConfigResponse> {
  return request<PlatformConfigResponse>("/api/v1/config/platform");
}

export function resetPlatformConfig(): Promise<PlatformResetResponse> {
  return request<PlatformResetResponse>("/api/v1/config/platform", {
    method: "DELETE",
  });
}

export function testConnection(
  payload: PlatformConfigRequest,
): Promise<ConnectionTestResponse> {
  return request<ConnectionTestResponse>("/api/v1/config/platform/test", {
    method: "POST",
    body: payload,
  });
}

export function listMetricMappings(): Promise<MetricMapping[]> {
  return request<MetricMapping[]>("/api/v1/config/metrics");
}

export function createMetricMapping(
  payload: MetricMappingRequest,
): Promise<MetricMapping> {
  return request<MetricMapping>("/api/v1/config/metrics", {
    method: "POST",
    body: payload,
  });
}

export function updateMetricMapping(
  metricName: CanonicalMetricName,
  payload: MetricMappingRequest,
): Promise<MetricMapping> {
  return request<MetricMapping>(`/api/v1/config/metrics/${metricName}`, {
    method: "PUT",
    body: payload,
  });
}

export async function deleteMetricMapping(
  metricName: CanonicalMetricName,
): Promise<void> {
  await request<unknown>(`/api/v1/config/metrics/${metricName}`, {
    method: "DELETE",
  });
}

export function testMetricMapping(
  payload: MetricMappingTestRequest,
): Promise<MetricMappingTestResponse> {
  return request<MetricMappingTestResponse>("/api/v1/config/metrics/test", {
    method: "POST",
    body: payload,
  });
}

export function listIntentBindings(): Promise<IntentBinding[]> {
  return request<IntentBinding[]>("/api/v1/config/intent-bindings");
}

export function createIntentBinding(
  payload: IntentBindingRequest,
): Promise<IntentBinding> {
  return request<IntentBinding>("/api/v1/config/intent-bindings", {
    method: "POST",
    body: payload,
  });
}

export function updateIntentBinding(
  intentName: string,
  payload: IntentBindingRequest,
): Promise<IntentBinding> {
  return request<IntentBinding>(`/api/v1/config/intent-bindings/${intentName}`, {
    method: "PUT",
    body: payload,
  });
}

export async function deleteIntentBinding(
  intentName: string,
): Promise<void> {
  await request<unknown>(`/api/v1/config/intent-bindings/${intentName}`, {
    method: "DELETE",
  });
}

export async function getIntents(): Promise<IntentListResponse> {
  const response = await request<
    IntentListResponse | { intents: IntentState[] }
  >("/api/v1/config/intents");
  const normalizeIntent = (intent: IntentState): IntentState => ({
    ...intent,
    category:
      intent.category === "action" || intent.category === "system"
        ? intent.category
        : "kpi",
  });
  if (Array.isArray(response)) {
    return response.map(normalizeIntent);
  }
  return (response.intents ?? []).map(normalizeIntent);
}

export function setIntentActive(
  intentName: string,
  active: boolean,
): Promise<IntentState> {
  return request<IntentState>(`/api/v1/config/intents/${intentName}`, {
    method: "PUT",
    body: { active },
  });
}

export function getSiteProgress(
  siteId: string = DEFAULT_SITE_ID,
): Promise<SiteProgressResponse> {
  return request<SiteProgressResponse>(`/api/v1/kpi/progress/${siteId}`);
}

export function getBaselines(
  siteId: string = DEFAULT_SITE_ID,
): Promise<BaselineResponse[]> {
  return request<BaselineResponse[]>(`/api/v1/kpi/baseline/${siteId}`);
}

export function getSnapshots(
  siteId: string,
  metric: string,
  startDate?: string,
  endDate?: string,
): Promise<SnapshotResponse[]> {
  const resolvedSiteId = siteId || DEFAULT_SITE_ID;
  const params = new URLSearchParams();
  if (startDate) {
    params.set("start_date", startDate);
  }
  if (endDate) {
    params.set("end_date", endDate);
  }

  const suffix = params.toString() ? `?${params.toString()}` : "";
  return request<SnapshotResponse[]>(
    `/api/v1/kpi/snapshots/${resolvedSiteId}/${metric}${suffix}`,
  );
}

export async function uploadProductionCSV(
  file: File,
): Promise<CSVUploadResponse> {
  const apiKey = getStoredApiKey();
  const formData = new FormData();
  formData.append("file", file);

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/production-data/bulk`, {
      method: "POST",
      headers: apiKey ? { "X-API-Key": apiKey } : undefined,
      body: formData,
    });
  } catch {
    throw new ApiError("Cannot connect to server", 0);
  }

  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }

  return (await response.json()) as CSVUploadResponse;
}

export function listProductionData(params?: {
  asset_id?: string;
  start_date?: string;
  end_date?: string;
}): Promise<ProductionRecordListResponse> {
  const search = new URLSearchParams();
  if (params?.asset_id) {
    search.set("asset_id", params.asset_id);
  }
  if (params?.start_date) {
    search.set("start_date", params.start_date);
  }
  if (params?.end_date) {
    search.set("end_date", params.end_date);
  }
  const suffix = search.toString() ? `?${search.toString()}` : "";
  return request<ProductionRecordListResponse>(
    `/api/v1/production-data${suffix}`,
  );
}

export function createProductionEntry(
  payload: ProductionRecordRequest,
): Promise<ProductionRecordResponse> {
  return request<ProductionRecordResponse>("/api/v1/production-data", {
    method: "POST",
    body: payload,
  });
}

export async function deleteProductionEntry(id: number): Promise<void> {
  await request<unknown>(`/api/v1/production-data/${id}`, {
    method: "DELETE",
  });
}

export async function downloadCSVTemplate(): Promise<Blob> {
  const apiKey = getStoredApiKey();
  const headers: Record<string, string> = {};
  if (apiKey) {
    headers["X-API-Key"] = apiKey;
  }
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/v1/production-data/template`, {
      method: "GET",
      headers,
    });
  } catch {
    throw new ApiError("Cannot connect to server", 0);
  }
  if (!response.ok) {
    const message = await parseErrorMessage(response);
    throw new ApiError(message, response.status);
  }
  return response.blob();
}

export function getProductionSummary(
  assetId: string,
  startDate: string,
  endDate: string,
): Promise<ProductionSummaryResponse> {
  const params = new URLSearchParams({
    asset_id: assetId,
    start_date: startDate,
    end_date: endDate,
  });
  return request<ProductionSummaryResponse>(
    `/api/v1/production-data/summary?${params.toString()}`,
  );
}

export function listEmissionFactors(): Promise<EmissionFactorListResponse> {
  return request<EmissionFactorListResponse>("/api/v1/config/emission-factors");
}

export function createEmissionFactor(
  payload: EmissionFactorRequest
): Promise<EmissionFactorResponse> {
  return request<EmissionFactorResponse>("/api/v1/config/emission-factors", {
    method: "POST",
    body: payload
  });
}

export async function deleteEmissionFactor(energySource: string): Promise<void> {
  await request<unknown>(`/api/v1/config/emission-factors/${energySource}`, {
    method: "DELETE"
  });
}

export function listEmissionFactorPresets(): Promise<EmissionFactorPresetResponse[]> {
  return request<EmissionFactorPresetResponse[]>(
    "/api/v1/config/emission-factors/presets"
  );
}

export function getVoiceConfig(): Promise<VoiceConfigResponse> {
  return request<VoiceConfigResponse>("/api/v1/voice/config");
}

// ── Profile API ────────────────────────────────────────

export function listProfiles(): Promise<ProfileListResponse> {
  return request<ProfileListResponse>("/api/v1/config/profiles");
}

export function getProfile(name: string): Promise<ProfileDetailResponse> {
  return request<ProfileDetailResponse>(`/api/v1/config/profiles/${name}`);
}

export function createProfile(
  payload: CreateProfileRequest,
): Promise<ProfileDetailResponse> {
  return request<ProfileDetailResponse>("/api/v1/config/profiles", {
    method: "POST",
    body: payload,
  });
}

export function updateProfile(
  name: string,
  payload: UpdateProfileRequest,
): Promise<ProfileDetailResponse> {
  return request<ProfileDetailResponse>(`/api/v1/config/profiles/${name}`, {
    method: "PUT",
    body: payload,
  });
}

export async function deleteProfile(
  name: string,
): Promise<DeleteProfileResponse> {
  return request<DeleteProfileResponse>(`/api/v1/config/profiles/${name}`, {
    method: "DELETE",
  });
}

export function activateProfile(
  name: string,
): Promise<ActivateProfileResponse> {
  return request<ActivateProfileResponse>(
    `/api/v1/config/profiles/${name}/activate`,
    { method: "POST" },
  );
}

export function discoverAssets(): Promise<AssetDiscoveryResponse> {
  return request<Record<string, unknown>>("/api/v1/assets/discover").then(
    normalizeDiscoveryResponse,
  );
}

export function getAssetLinkingSummary(): Promise<AssetLinkingSummaryResponse> {
  return request<AssetLinkingSummaryResponse>("/api/v1/assets/linking-summary").catch(
    async (error: unknown) => {
      if (!(error instanceof ApiError) || error.status !== 404) {
        throw error;
      }
      return buildLegacyAssetLinkingSummary();
    },
  );
}

export function getConfiguredAssets(): Promise<AssetMappingsResponse> {
  return request<AssetMappingsResponse>("/api/v1/config/assets");
}

export function saveConfiguredAssets(
  assetMappings: AssetMappingsResponse["asset_mappings"],
): Promise<AssetMappingsResponse> {
  return request<AssetMappingsResponse>("/api/v1/config/assets", {
    method: "POST",
    body: { asset_mappings: assetMappings },
  });
}

export function importGeneratorMapping(
  mapping: Record<string, Record<string, string>>,
): Promise<GeneratorMappingResponse> {
  return request<GeneratorMappingResponse>("/api/v1/assets/import-generator-mapping", {
    method: "POST",
    body: { mapping },
  });
}

// Backward-compatible aliases for existing callers.
export const getAssetMappings = getConfiguredAssets;
export const setAssetMappings = saveConfiguredAssets;

type LegacySeu = {
  id?: string;
  name?: string;
  energy_resource?: string;
};

type LegacyDiscovery = {
  seus?: LegacySeu[];
  existing_mappings?: Record<string, AssetMappingItem>;
  platform_type?: string;
  supports_discovery?: boolean;
  assets?: AssetRecord[];
  registered_assets?: AssetRecord[];
  discovery_source?: "adapter" | "registered" | "none";
  discovery_error?: string;
};

function normalizeDiscoveryResponse(
  payload: Record<string, unknown>,
): AssetDiscoveryResponse {
  const data = payload as LegacyDiscovery;
  const isLegacySeuPayload = Array.isArray(data.seus);
  if (!isLegacySeuPayload) {
    const nativeAssets = Array.isArray(data.assets) ? data.assets : [];
    const registeredAssets = Array.isArray(data.registered_assets)
      ? data.registered_assets
      : [];
    const inferredSource =
      nativeAssets.length > 0
        ? "adapter"
        : registeredAssets.length > 0
        ? "registered"
        : "none";
    return {
      platform_type:
        (data.platform_type as AssetDiscoveryResponse["platform_type"]) ?? "mock",
      supports_discovery: Boolean(data.supports_discovery),
      discovery_source: data.discovery_source ?? inferredSource,
      assets: nativeAssets,
      registered_assets: registeredAssets,
      discovery_error: String(data.discovery_error ?? ""),
      existing_mappings: data.existing_mappings ?? {},
    };
  }

  const legacySeus = Array.isArray(data.seus) ? data.seus : [];
  const assets: AssetRecord[] = legacySeus
    .filter((item) => typeof item?.id === "string" && item.id.length > 0)
    .map((item) => ({
      asset_id: item.id as string,
      display_name: (item.name as string) || (item.id as string),
      asset_type: "seu",
      aliases: [
        ((item.name as string) || "").trim(),
        (item.id as string).trim(),
      ].filter(Boolean),
      metadata: {
        energy_resource: (item.energy_resource as string) || "",
      },
    }));

  return {
    platform_type:
      (data.platform_type as AssetDiscoveryResponse["platform_type"]) ?? "reneryo",
    supports_discovery:
      typeof data.supports_discovery === "boolean"
        ? data.supports_discovery
        : true,
    discovery_source: assets.length > 0 ? "adapter" : "none",
    assets,
    registered_assets: [],
    discovery_error: String(data.discovery_error ?? ""),
    existing_mappings: data.existing_mappings ?? {},
  };
}

function normalizeMetricResources(
  value: unknown,
): Partial<Record<CanonicalMetricName, string>> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }
  const output: Partial<Record<CanonicalMetricName, string>> = {};
  for (const [metricName, resourceId] of Object.entries(
    value as Record<string, unknown>,
  )) {
    if (!CANONICAL_METRIC_NAMES.includes(metricName as CanonicalMetricName)) {
      continue;
    }
    const resource = String(resourceId ?? "").trim();
    if (!resource) {
      continue;
    }
    output[metricName as CanonicalMetricName] = resource;
  }
  return output;
}

function normalizeAssetType(value: unknown): "machine" | "line" | "sensor" | "seu" {
  if (value === "line" || value === "sensor" || value === "seu") {
    return value;
  }
  return "machine";
}

function normalizeAliases(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value
    .map((alias) => String(alias ?? "").trim())
    .filter((alias) => alias.length > 0);
}

function normalizeAssetKey(assetId: string): string {
  return assetId.toLowerCase().replace(/[^a-z0-9]/g, "");
}

async function buildLegacyAssetLinkingSummary(): Promise<AssetLinkingSummaryResponse> {
  const [mappingsResponse, discovery] = await Promise.all([
    getConfiguredAssets(),
    discoverAssets().catch(() => null),
  ]);

  const mappings = mappingsResponse.asset_mappings ?? {};
  const importedAssets: AssetLinkingSummaryResponse["imported_assets"] = [];
  const unlinkedAssets: AssetLinkingSummaryResponse["unlinked_assets"] = [];

  for (const assetId of Object.keys(mappings).sort()) {
    const mapping = mappings[assetId] ?? {};
    const normalizedResources = normalizeMetricResources(mapping.metric_resources);
    const linkedMetrics = Object.keys(normalizedResources).sort() as CanonicalMetricName[];
    const missingMetrics = CANONICAL_METRIC_NAMES.filter(
      (metric) => !linkedMetrics.includes(metric),
    );

    const item = {
      asset_id: assetId,
      display_name: String(mapping.display_name ?? assetId),
      asset_type: normalizeAssetType(mapping.asset_type),
      aliases: normalizeAliases(mapping.aliases),
      source: linkedMetrics.length > 0 ? "imported" : "registered",
      linked_metrics: linkedMetrics,
      missing_metrics: missingMetrics,
      linked_metric_count: linkedMetrics.length,
      total_metrics: CANONICAL_METRIC_NAMES.length,
    } as const;

    if (linkedMetrics.length > 0) {
      importedAssets.push(item);
    } else {
      unlinkedAssets.push(item);
    }
  }

  const existingKeys = new Set(
    [...importedAssets, ...unlinkedAssets].map((item) =>
      normalizeAssetKey(item.asset_id),
    ),
  );
  const discoveredAssets: AssetLinkingSummaryResponse["discovered_assets"] = (
    discovery?.assets ?? []
  )
    .filter((asset) => !existingKeys.has(normalizeAssetKey(asset.asset_id)))
    .map((asset) => ({
      asset_id: asset.asset_id,
      display_name: asset.display_name || asset.asset_id,
      asset_type: normalizeAssetType(asset.asset_type),
      aliases: normalizeAliases(asset.aliases),
      source: "discovered" as const,
      linked_metrics: [],
      missing_metrics: CANONICAL_METRIC_NAMES,
      linked_metric_count: 0,
      total_metrics: CANONICAL_METRIC_NAMES.length,
    }));

  const metricCoverage = CANONICAL_METRIC_NAMES.map((metric) => {
    const linkedAssets = importedAssets.filter((item) =>
      item.linked_metrics.includes(metric),
    );
    const missingAssets = importedAssets
      .filter((item) => !item.linked_metrics.includes(metric))
      .map((item) => item.asset_id);
    return {
      metric_name: metric,
      linked_assets: linkedAssets.length,
      total_assets: importedAssets.length,
      missing_assets: missingAssets,
    };
  });

  return {
    platform_type: discovery?.platform_type ?? "custom_rest",
    supports_discovery: discovery?.supports_discovery ?? false,
    discovery_source: discovery?.discovery_source ?? "registered",
    discovery_error: discovery?.discovery_error ?? "",
    canonical_metrics: CANONICAL_METRIC_NAMES,
    imported_assets: importedAssets,
    unlinked_assets: unlinkedAssets,
    discovered_assets: discoveredAssets,
    metric_coverage: metricCoverage,
  };
}
