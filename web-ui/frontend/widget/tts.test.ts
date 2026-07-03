// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import {
  WIDGET_TTS_CHUNK_MAX_CHARS,
  resolveServerTtsUrl,
  splitWidgetTtsText,
} from "./tts";

describe("widget TTS helpers", () => {
  it("splits long responses without breaking decimal KPI values", () => {
    const chunks = splitWidgetTtsText(
      "Next week, energy per unit on Line-1 is expected to be 1.7 kilowatt hours. " +
        "That is 20.5 percent lower than the latest observed value of 2.1 kilowatt hours. " +
        "Confidence is low because recent data is noisy, so treat this as an early warning.",
    );

    expect(chunks.length).toBeGreaterThan(1);
    expect(chunks.every((chunk) => chunk.length <= WIDGET_TTS_CHUNK_MAX_CHARS)).toBe(
      true,
    );
    expect(chunks.join(" ")).toContain("1.7 kilowatt hours");
    expect(chunks.join(" ")).toContain("20.5 percent");
    expect(chunks.join(" ")).toContain("2.1 kilowatt hours");
  });

  it("keeps the first forecast sentence separate for lower playback latency", () => {
    const chunks = splitWidgetTtsText(
      "Next week, energy per unit on Line-3 is expected to be 1.7 kilowatt hours. " +
        "That is 14.7 percent lower than the latest observed value of 2.0 kilowatt hours. " +
        "For this KPI, that points to a possible improvement.",
    );

    expect(chunks[0]).toBe(
      "Next week, energy per unit on Line-3 is expected to be 1.7 kilowatt hours.",
    );
  });

  it("resolves the widget TTS endpoint from the configured AVAROS URL", () => {
    expect(resolveServerTtsUrl("https://avaros.reneryo.com/base")).toBe(
      "https://avaros.reneryo.com/voice/tts",
    );
  });
});
