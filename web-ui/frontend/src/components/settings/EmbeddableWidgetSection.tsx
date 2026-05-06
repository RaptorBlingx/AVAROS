import { useCallback, useEffect, useMemo, useState } from "react";

import { getVoiceConfig, toFriendlyErrorMessage } from "../../api/client";
import type { VoiceConfigResponse } from "../../api/types";

type EmbeddableWidgetSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";
type WidgetTheme = "auto" | "light" | "dark";
type WidgetSize = "small" | "medium" | "large";

function attr(value: string): string {
  return value
    .replace(/&/g, "&amp;")
    .replace(/"/g, "&quot;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;");
}

function currentOrigin(): string {
  if (typeof window === "undefined") return "";
  return window.location.origin;
}

function buildWidgetSnippet({
  origin,
  voiceConfig,
  position,
  theme,
  size,
  label,
}: {
  origin: string;
  voiceConfig: VoiceConfigResponse | null;
  position: WidgetPosition;
  theme: WidgetTheme;
  size: WidgetSize;
  label: string;
}): string {
  const scriptSrc = `${origin.replace(/\/$/, "")}/avaros-widget.js`;
  const hivemindUrl = voiceConfig?.hivemind_url ?? "";
  const clientName = voiceConfig?.hivemind_name || "avaros-web-client";
  const accessKey = voiceConfig?.hivemind_key ?? "";

  return `<script
  async
  src="${attr(scriptSrc)}"
  data-host="${attr(hivemindUrl)}"
  data-client-name="${attr(clientName)}"
  data-access-key="${attr(accessKey)}"
  data-position="${position}"
  data-theme="${theme}"
  data-size="${size}"
  data-label="${attr(label)}"
  data-disabled-modes="wake-word">
</script>`;
}

async function copyText(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }

  const textarea = document.createElement("textarea");
  textarea.value = text;
  textarea.setAttribute("readonly", "true");
  textarea.style.position = "fixed";
  textarea.style.left = "-9999px";
  document.body.appendChild(textarea);
  textarea.select();
  const copied = document.execCommand("copy");
  textarea.remove();
  if (!copied) {
    throw new Error("Clipboard copy failed");
  }
}

export default function EmbeddableWidgetSection({
  onNotify,
}: EmbeddableWidgetSectionProps) {
  const [voiceConfig, setVoiceConfig] = useState<VoiceConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [position, setPosition] = useState<WidgetPosition>("bottom-right");
  const [theme, setTheme] = useState<WidgetTheme>("auto");
  const [size, setSize] = useState<WidgetSize>("medium");
  const [label, setLabel] = useState("Ask AVAROS");

  const loadConfig = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const config = await getVoiceConfig();
      setVoiceConfig(config);
    } catch (err) {
      setError(toFriendlyErrorMessage(err));
      setVoiceConfig(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadConfig();
  }, [loadConfig]);

  const snippet = useMemo(
    () =>
      buildWidgetSnippet({
        origin: currentOrigin(),
        voiceConfig,
        position,
        theme,
        size,
        label,
      }),
    [label, position, size, theme, voiceConfig],
  );

  const ready = Boolean(voiceConfig?.voice_enabled && voiceConfig.hivemind_key);

  const handleCopy = useCallback(async () => {
    try {
      await copyText(snippet);
      onNotify("success", "Widget embed snippet copied.");
    } catch {
      onNotify("error", "Could not copy snippet. Select the code manually.");
    }
  }, [onNotify, snippet]);

  return (
    <div className="space-y-4">
      <div className="rounded-xl border border-cyan-100 bg-cyan-50/60 p-4 text-sm text-slate-700 dark:border-cyan-900/50 dark:bg-cyan-950/30 dark:text-slate-200">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="m-0 text-xs font-semibold uppercase tracking-[0.14em] text-cyan-700 dark:text-cyan-300">
              Internal Trusted Embed
            </p>
            <h3 className="m-0 mt-1 text-base font-semibold text-slate-900 dark:text-slate-50">
              Embeddable Widget
            </h3>
            <p className="m-0 mt-2 max-w-3xl">
              Add this widget to a trusted factory dashboard or intranet page
              after AVAROS voice/HiveMind is configured. The access key is
              visible in browser HTML, so do not use this v1 snippet on public
              internet pages.
            </p>
          </div>
          <span
            className={`rounded-full px-3 py-1 text-xs font-semibold ${
              ready
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/40 dark:text-emerald-200"
                : "bg-amber-100 text-amber-700 dark:bg-amber-900/40 dark:text-amber-200"
            }`}
          >
            {loading ? "Checking..." : ready ? "Ready" : "Not ready"}
          </span>
        </div>
      </div>

      {error ? (
        <p className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700 dark:border-red-900/60 dark:bg-red-950/30 dark:text-red-200">
          {error}
        </p>
      ) : null}

      {!loading && !ready ? (
        <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-800 dark:border-amber-900/60 dark:bg-amber-950/30 dark:text-amber-100">
          Widget embed is not ready because HiveMind voice access is not
          configured. Set `HIVEMIND_CLIENT_KEY` and restart the Web UI stack,
          then refresh this section.
        </p>
      ) : null}

      <div className="grid gap-3 md:grid-cols-4">
        <label className="space-y-1 text-sm font-medium text-slate-700 dark:text-slate-200">
          Position
          <select
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            value={position}
            onChange={(event) => setPosition(event.target.value as WidgetPosition)}
          >
            <option value="bottom-right">Bottom right</option>
            <option value="bottom-left">Bottom left</option>
            <option value="top-right">Top right</option>
            <option value="top-left">Top left</option>
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium text-slate-700 dark:text-slate-200">
          Theme
          <select
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            value={theme}
            onChange={(event) => setTheme(event.target.value as WidgetTheme)}
          >
            <option value="auto">Auto</option>
            <option value="light">Light</option>
            <option value="dark">Dark</option>
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium text-slate-700 dark:text-slate-200">
          Size
          <select
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            value={size}
            onChange={(event) => setSize(event.target.value as WidgetSize)}
          >
            <option value="small">Small</option>
            <option value="medium">Medium</option>
            <option value="large">Large</option>
          </select>
        </label>
        <label className="space-y-1 text-sm font-medium text-slate-700 dark:text-slate-200">
          Label
          <input
            className="w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-900"
            value={label}
            maxLength={40}
            onChange={(event) => setLabel(event.target.value)}
          />
        </label>
      </div>

      <div className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="m-0 text-sm font-semibold text-slate-700 dark:text-slate-200">
            Copy-paste script tag
          </p>
          <div className="flex gap-2">
            <button
              type="button"
              className="btn-brand-subtle rounded-lg px-3 py-2 text-sm font-semibold"
              onClick={() => void loadConfig()}
            >
              Refresh Config
            </button>
            <button
              type="button"
              className="btn-brand-primary rounded-lg px-3 py-2 text-sm font-semibold"
              onClick={() => void handleCopy()}
              disabled={!ready}
            >
              Copy Snippet
            </button>
          </div>
        </div>
        <pre className="max-h-72 overflow-auto rounded-xl border border-slate-200 bg-slate-950 p-4 text-xs leading-5 text-slate-50 dark:border-slate-700">
          <code>{snippet}</code>
        </pre>
      </div>

      <p className="m-0 text-xs text-slate-500 dark:text-slate-400">
        Voice capture requires HTTPS or localhost. Wake-word mode is disabled
        by default for embedded v1; users can still type or use push-to-talk.
      </p>
    </div>
  );
}

export { buildWidgetSnippet };
