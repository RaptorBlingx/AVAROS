import { createRoot } from "react-dom/client";

import { Widget } from "./Widget";
import { readWidgetConfig, resolveScriptElement } from "./config";
import styleText from "./styles.css?inline";
import type { WidgetPublicApi } from "./types";

declare global {
  interface Window {
    AvarosWidget?: WidgetPublicApi;
  }
}

const ROOT_ID = "avaros-widget-root";

function bootstrap(): void {
  const script = resolveScriptElement();
  if (!script) return;

  const existing = document.getElementById(ROOT_ID);
  if (existing) return;

  const { config, configError } = readWidgetConfig(script);
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
