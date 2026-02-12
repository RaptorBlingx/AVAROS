import type {
  BaselineResponse,
  CanonicalMetricName,
  ConnectionTestResponse,
  HealthResponse,
  IntentListResponse,
  IntentState,
  MetricMapping,
  MetricMappingRequest,
  PlatformConfigRequest,
  PlatformConfigResponse,
  PlatformResetResponse,
  SiteProgressResponse,
  SnapshotResponse,
  SystemStatusResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
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

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json"
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
      body: options.body ? JSON.stringify(options.body) : undefined
    });
  } catch {
    throw new ApiError("Cannot connect to server", 0);
  }

  if (!response.ok) {
    let message = "Request failed";
    try {
      const data = (await response.json()) as { detail?: unknown };
      if (typeof data.detail === "string") {
        message = data.detail;
      } else if (Array.isArray(data.detail) && data.detail.length > 0) {
        const item = data.detail[0] as { msg?: string };
        message = item.msg ?? message;
      }
    } catch {
      message = "Request failed";
    }
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
  payload: PlatformConfigRequest
): Promise<PlatformConfigResponse> {
  return request<PlatformConfigResponse>("/api/v1/config/platform", {
    method: "POST",
    body: payload
  });
}

export function getPlatformConfig(): Promise<PlatformConfigResponse> {
  return request<PlatformConfigResponse>("/api/v1/config/platform");
}

export function resetPlatformConfig(): Promise<PlatformResetResponse> {
  return request<PlatformResetResponse>("/api/v1/config/platform", {
    method: "DELETE"
  });
}

export function testConnection(
  payload: PlatformConfigRequest
): Promise<ConnectionTestResponse> {
  return request<ConnectionTestResponse>("/api/v1/config/platform/test", {
    method: "POST",
    body: payload
  });
}

export function listMetricMappings(): Promise<MetricMapping[]> {
  return request<MetricMapping[]>("/api/v1/config/metrics");
}

export function createMetricMapping(
  payload: MetricMappingRequest
): Promise<MetricMapping> {
  return request<MetricMapping>("/api/v1/config/metrics", {
    method: "POST",
    body: payload
  });
}

export function updateMetricMapping(
  metricName: CanonicalMetricName,
  payload: MetricMappingRequest
): Promise<MetricMapping> {
  return request<MetricMapping>(`/api/v1/config/metrics/${metricName}`, {
    method: "PUT",
    body: payload
  });
}

export async function deleteMetricMapping(
  metricName: CanonicalMetricName
): Promise<void> {
  await request<unknown>(`/api/v1/config/metrics/${metricName}`, {
    method: "DELETE"
  });
}

export async function getIntents(): Promise<IntentListResponse> {
  const response = await request<IntentListResponse | { intents: IntentState[] }>(
    "/api/v1/config/intents"
  );
  if (Array.isArray(response)) {
    return response;
  }
  return response.intents ?? [];
}

export function setIntentActive(
  intentName: string,
  active: boolean
): Promise<IntentState> {
  return request<IntentState>(`/api/v1/config/intents/${intentName}`, {
    method: "PUT",
    body: { active }
  });
}

export function getSiteProgress(
  siteId: string = DEFAULT_SITE_ID
): Promise<SiteProgressResponse> {
  return request<SiteProgressResponse>(`/api/v1/kpi/progress/${siteId}`);
}

export function getBaselines(
  siteId: string = DEFAULT_SITE_ID
): Promise<BaselineResponse[]> {
  return request<BaselineResponse[]>(`/api/v1/kpi/baseline/${siteId}`);
}

export function getSnapshots(
  siteId: string,
  metric: string,
  startDate?: string,
  endDate?: string
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
    `/api/v1/kpi/snapshots/${resolvedSiteId}/${metric}${suffix}`
  );
}
