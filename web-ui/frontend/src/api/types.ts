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

export type ConnectionTestResponse = {
  success: boolean;
  message: string;
};
