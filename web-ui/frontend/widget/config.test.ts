// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  parseDisabledModes,
  readWidgetConfig,
  resolveWidgetAssetUrl,
} from "./config";

function makeScript(src = "https://avaros.example.com/avaros-widget.js") {
  const script = document.createElement("script");
  script.src = src;
  script.dataset.host = "wss://avaros.example.com/hivemind/";
  script.dataset.accessKey = "widget-key";
  return script;
}

describe("widget config", () => {
  it("defaults wake-word off for trusted internal v1 embeds", () => {
    expect(parseDisabledModes(undefined)).toEqual(["wake-word"]);

    const { config } = readWidgetConfig(makeScript());

    expect(config.disabledModes).toEqual(["wake-word"]);
  });

  it("resolves widget assets relative to the script URL", () => {
    const script = makeScript("https://avaros.example.com/static/avaros-widget.js");

    expect(resolveWidgetAssetUrl(script, "widget-logo.svg")).toBe(
      "https://avaros.example.com/static/widget-logo.svg",
    );
  });

  it("keeps explicit disabled modes from the host script", () => {
    const script = makeScript();
    script.dataset.disabledModes = "wake-word,text";

    const { config } = readWidgetConfig(script);

    expect(config.disabledModes).toEqual(["wake-word", "text"]);
  });
});
