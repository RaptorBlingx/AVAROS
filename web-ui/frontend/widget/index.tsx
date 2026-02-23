import { createRoot } from "react-dom/client";

import { Widget } from "./Widget";
import styleText from "./styles.css?inline";
import type { WidgetConfig, WidgetMode, WidgetPublicApi } from "./types";

declare global {
  interface Window {
    AvarosWidget?: WidgetPublicApi;
  }
}

const ROOT_ID = "avaros-widget-root";

function parsePosition(value: string | undefined): WidgetConfig["position"] {
  if (
    value === "bottom-left" ||
    value === "top-right" ||
    value === "top-left" ||
    value === "bottom-right"
  ) {
    return value;
  }
  return "bottom-right";
}

function parseTheme(value: string | undefined): WidgetConfig["theme"] {
  if (value === "light" || value === "dark" || value === "auto") {
    return value;
  }
  return "auto";
}

function parseSize(value: string | undefined): WidgetConfig["size"] {
  if (value === "small" || value === "medium" || value === "large") {
    return value;
  }
  return "medium";
}

function parseOffset(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, parsed);
}

function parseDisabledModes(value: string | undefined): WidgetMode[] {
  if (!value) return [];
  const parts = value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  const modes = new Set<WidgetMode>();
  parts.forEach((part) => {
    if (part === "wake-word" || part === "push-to-talk" || part === "text") {
      modes.add(part);
    }
  });
  return Array.from(modes);
}

function resolveScriptElement(): HTMLScriptElement | null {
  if (
    document.currentScript &&
    document.currentScript instanceof HTMLScriptElement
  ) {
    return document.currentScript;
  }

  const scripts = Array.from(
    document.querySelectorAll(
      'script[src*="avaros-widget.js"], script[src*="/widget/index.tsx"], script[data-widget-loader="true"]',
    ),
  );
  const last = scripts[scripts.length - 1];
  return last instanceof HTMLScriptElement ? last : null;
}

function readConfig(script: HTMLScriptElement): {
  config: WidgetConfig;
  configError: string | null;
} {
  const host = script.dataset.host?.trim() ?? "";
  const clientName = script.dataset.clientName?.trim() || "avaros-web-client";
  const accessKey = script.dataset.accessKey?.trim() ?? "";
  const accessSecret = script.dataset.accessSecret?.trim() ?? "";
  const encryptionKey = script.dataset.encryptionKey?.trim() ?? "";
  const configError =
    !host || !accessKey
      ? "Configuration error: data-host and data-access-key required"
      : null;

  return {
    config: {
      host,
      clientName,
      accessKey,
      accessSecret,
      encryptionKey,
      position: parsePosition(script.dataset.position),
      theme: parseTheme(script.dataset.theme),
      size: parseSize(script.dataset.size),
      offsetX: parseOffset(script.dataset.offsetX, 20),
      offsetY: parseOffset(script.dataset.offsetY, 20),
      label: script.dataset.label?.trim() ?? "",
      disabledModes: parseDisabledModes(script.dataset.disabledModes),
    },
    configError,
  };
}

function bootstrap(): void {
  const script = resolveScriptElement();
  if (!script) return;

  const existing = document.getElementById(ROOT_ID);
  if (existing) return;

  const { config, configError } = readConfig(script);
  const host = document.createElement("div");
  host.id = ROOT_ID;
  document.body.appendChild(host);

  const shadowRoot = host.attachShadow({ mode: "open" });
  const styleEl = document.createElement("style");
  styleEl.textContent = styleText;
  shadowRoot.appendChild(styleEl);

  const container = document.createElement("div");
  shadowRoot.appendChild(container);
  const root = createRoot(container);

  const runtimeApi: Omit<WidgetPublicApi, "destroy"> = {
    open: () => undefined,
    close: () => undefined,
    send: () => undefined,
    isConnected: () => false,
    activateVoice: () => undefined,
  };

  const destroy = () => {
    root.unmount();
    host.remove();
    if (window.AvarosWidget?.destroy === destroy) {
      window.AvarosWidget = undefined;
    }
  };

  window.AvarosWidget = {
    open: () => runtimeApi.open(),
    close: () => runtimeApi.close(),
    send: (text: string) => runtimeApi.send(text),
    isConnected: () => runtimeApi.isConnected(),
    activateVoice: () => runtimeApi.activateVoice(),
    destroy,
  };

  root.render(
    <Widget
      config={config}
      configError={configError}
      onReady={(api) => {
        runtimeApi.open = api.open;
        runtimeApi.close = api.close;
        runtimeApi.send = api.send;
        runtimeApi.isConnected = api.isConnected;
        runtimeApi.activateVoice = api.activateVoice;
      }}
    />,
  );
}

bootstrap();
