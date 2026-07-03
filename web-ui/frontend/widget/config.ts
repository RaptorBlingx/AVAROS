import type {
  WidgetConfig,
  WidgetDefaultMode,
  WidgetMode,
  WidgetTtsEngine,
} from "./types";

export const DEFAULT_DISABLED_MODES: WidgetMode[] = ["wake-word"];

export function parsePosition(value: string | undefined): WidgetConfig["position"] {
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

export function parseTheme(value: string | undefined): WidgetConfig["theme"] {
  if (value === "light" || value === "dark" || value === "auto") {
    return value;
  }
  return "auto";
}

export function parseSize(value: string | undefined): WidgetConfig["size"] {
  if (value === "small" || value === "medium" || value === "large") {
    return value;
  }
  return "medium";
}

export function parseOffset(value: string | undefined, fallback: number): number {
  if (!value) return fallback;
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, parsed);
}

export function parseDisabledModes(value: string | undefined): WidgetMode[] {
  if (!value) return [...DEFAULT_DISABLED_MODES];
  const parts = value
    .split(",")
    .map((part) => part.trim())
    .filter(Boolean);
  if (parts.some((part) => part.toLowerCase() === "none")) return [];
  const modes = new Set<WidgetMode>();
  parts.forEach((part) => {
    if (part === "wake-word" || part === "push-to-talk" || part === "text") {
      modes.add(part);
    }
  });
  return Array.from(modes);
}

export function parseDefaultMode(
  value: string | undefined,
): WidgetDefaultMode | undefined {
  if (value === "inherit") return value;
  if (value === "wake-word" || value === "push-to-talk" || value === "text") {
    return value;
  }
  return undefined;
}

export function parseTtsEngine(
  value: string | undefined,
  meetingAudio: string | undefined,
): WidgetTtsEngine {
  const normalized = value?.trim().toLowerCase();
  if (normalized === "server" || normalized === "meeting") return "server";
  if (normalized === "browser") return "browser";
  if (meetingAudio?.trim().toLowerCase() === "true") return "server";
  return "server";
}

export function resolveWidgetAssetUrl(
  script: HTMLScriptElement,
  assetPath: string,
): string {
  const trimmed = assetPath.trim();
  if (!trimmed) return "";
  const base = script.src || window.location.href;
  try {
    return new URL(trimmed, base).toString();
  } catch {
    return trimmed;
  }
}

export function resolveWidgetOriginUrl(script: HTMLScriptElement): string {
  try {
    return new URL("/", script.src || window.location.href).toString();
  } catch {
    return window.location.origin ? `${window.location.origin}/` : "/";
  }
}

function toWebSocketUrl(httpUrl: string): string {
  const parsed = new URL(httpUrl);
  if (parsed.protocol === "https:") parsed.protocol = "wss:";
  if (parsed.protocol === "http:") parsed.protocol = "ws:";
  return parsed.toString();
}

export function resolveWakeWordUrl(
  script: HTMLScriptElement,
  avarosUrl: string,
): string {
  const explicit = script.dataset.wakeWordUrl?.trim();
  if (explicit) {
    try {
      return new URL(explicit, window.location.href).toString();
    } catch {
      return explicit;
    }
  }

  try {
    return toWebSocketUrl(new URL("/wakeword/ws/detect", avarosUrl).toString());
  } catch {
    return toWebSocketUrl(
      new URL("/wakeword/ws/detect", resolveWidgetOriginUrl(script)).toString(),
    );
  }
}

export function resolveScriptElement(): HTMLScriptElement | null {
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

export function readWidgetConfig(script: HTMLScriptElement): {
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
  const logoSrc = resolveWidgetAssetUrl(
    script,
    script.dataset.logoSrc?.trim() || "widget-logo.svg",
  );
  const avarosUrl = script.dataset.avarosUrl?.trim() || resolveWidgetOriginUrl(script);
  const defaultMode = parseDefaultMode(
    script.dataset.defaultMode?.trim() || script.dataset.voiceMode?.trim(),
  );

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
      defaultMode,
      logoSrc,
      avarosUrl,
      wakeWordUrl: resolveWakeWordUrl(script, avarosUrl),
      ttsEngine: parseTtsEngine(
        script.dataset.ttsEngine,
        script.dataset.meetingAudio,
      ),
    },
    configError,
  };
}
