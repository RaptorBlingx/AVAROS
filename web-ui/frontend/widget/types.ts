export type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

export type WidgetTheme = "light" | "dark" | "auto";
export type WidgetSize = "small" | "medium" | "large";
export type WidgetMode = "wake-word" | "push-to-talk" | "text";

export type WidgetConnectionState =
  | "disconnected"
  | "connecting"
  | "connected"
  | "error";

export type WidgetVisualState =
  | "idle"
  | "listening"
  | "processing"
  | "speaking"
  | "error"
  | "disabled";

export type ChatMessage = {
  id: string;
  source: "user" | "avaros";
  text: string;
  timestamp: Date;
};

export type WidgetConfig = {
  host: string;
  clientName: string;
  accessKey: string;
  accessSecret?: string;
  encryptionKey?: string;
  position: WidgetPosition;
  theme: WidgetTheme;
  size: WidgetSize;
  offsetX: number;
  offsetY: number;
  label: string;
  disabledModes: WidgetMode[];
};

export type WidgetPublicApi = {
  open: () => void;
  close: () => void;
  destroy: () => void;
  send: (text: string) => void;
  isConnected: () => boolean;
};
