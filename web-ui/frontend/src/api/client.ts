import type {
  ConnectionTestResponse,
  HealthResponse,
  PlatformConfigRequest,
  PlatformConfigResponse,
  SystemStatusResponse
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";
const API_KEY_STORAGE_KEY = "avaros_api_key";

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

export function testConnection(
  payload: PlatformConfigRequest
): Promise<ConnectionTestResponse> {
  return request<ConnectionTestResponse>("/api/v1/config/platform/test", {
    method: "POST",
    body: payload
  });
}
