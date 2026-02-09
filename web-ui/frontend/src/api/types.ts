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
