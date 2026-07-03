// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  parseDisabledModes,
  parseTtsEngine,
  readWidgetConfig,
  resolveWidgetAssetUrl,
  resolveWidgetOriginUrl,
  resolveWakeWordUrl,
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
    expect(resolveWidgetOriginUrl(script)).toBe("https://avaros.example.com/");
  });

  it("uses an explicit AVAROS URL when provided", () => {
    const script = makeScript();
    script.dataset.avarosUrl = "https://assistant.example.com/";

    const { config } = readWidgetConfig(script);

    expect(config.avarosUrl).toBe("https://assistant.example.com/");
    expect(config.wakeWordUrl).toBe(
      "wss://assistant.example.com/wakeword/ws/detect",
    );
  });

  it("keeps explicit disabled modes from the host script", () => {
    const script = makeScript();
    script.dataset.disabledModes = "wake-word,text";

    const { config } = readWidgetConfig(script);

    expect(config.disabledModes).toEqual(["wake-word", "text"]);
  });

  it("allows embeds to enable every mode explicitly", () => {
    const script = makeScript();
    script.dataset.disabledModes = "none";

    const { config } = readWidgetConfig(script);

    expect(config.disabledModes).toEqual([]);
  });

  it("keeps an explicit default mode from the host script", () => {
    const script = makeScript();
    script.dataset.defaultMode = "wake-word";

    const { config } = readWidgetConfig(script);

    expect(config.defaultMode).toBe("wake-word");
  });

  it("allows embeds to inherit the AVAROS voice mode", () => {
    const script = makeScript();
    script.dataset.defaultMode = "inherit";

    const { config } = readWidgetConfig(script);

    expect(config.defaultMode).toBe("inherit");
  });

  it("uses an explicit wake-word URL when provided", () => {
    const script = makeScript();
    script.dataset.wakeWordUrl = "wss://wakeword.example.com/ws/detect";

    expect(resolveWakeWordUrl(script, "https://assistant.example.com/")).toBe(
      "wss://wakeword.example.com/ws/detect",
    );
  });

  it("defaults to server TTS for meeting-safe playback", () => {
    expect(parseTtsEngine(undefined, undefined)).toBe("server");

    const { config } = readWidgetConfig(makeScript());

    expect(config.ttsEngine).toBe("server");
  });

  it("allows meeting audio to opt into server TTS explicitly", () => {
    expect(parseTtsEngine("server", undefined)).toBe("server");
    expect(parseTtsEngine("meeting", undefined)).toBe("server");
    expect(parseTtsEngine(undefined, "true")).toBe("server");

    const script = makeScript();
    script.dataset.ttsEngine = "server";

    const { config } = readWidgetConfig(script);

    expect(config.ttsEngine).toBe("server");
  });

  it("allows embeds to opt back into browser TTS explicitly", () => {
    expect(parseTtsEngine("browser", undefined)).toBe("browser");

    const script = makeScript();
    script.dataset.ttsEngine = "browser";

    const { config } = readWidgetConfig(script);

    expect(config.ttsEngine).toBe("browser");
  });
});
