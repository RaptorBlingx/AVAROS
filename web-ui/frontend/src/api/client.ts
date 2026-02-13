import type {
  BaselineResponse,
  CSVUploadResponse,
  CanonicalMetricName,
  ConnectionTestResponse,
  EmissionFactorListResponse,
  EmissionFactorPresetResponse,
  EmissionFactorRequest,
  EmissionFactorResponse,
  HealthResponse,
  IntentListResponse,
  IntentState,
  MetricMapping,
  MetricMappingRequest,
  PlatformConfigRequest,
  PlatformConfigResponse,
  PlatformResetResponse,
  ProductionRecordListResponse,
  ProductionRecordRequest,
  ProductionRecordResponse,
  ProductionSummaryResponse,
  SiteProgressResponse,
  SnapshotResponse,
  SystemStatusResponse,
} from "./types";

const API_BASE_URL = "";
const API_KEY_STORAGE_KEY = "avaros_api_key";
export const DEFAULT_SITE_ID = "pilot-1";

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

export async function getIntents(): Promise<IntentListResponse> {
  const response = await request<
    IntentListResponse | { intents: IntentState[] }
  >("/api/v1/config/intents");
  if (Array.isArray(response)) {
    return response;
  }
  return response.intents ?? [];
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
