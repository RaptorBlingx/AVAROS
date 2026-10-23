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

  it("keeps Turkish spoken numbers together with their units", () => {
    const text = "Eylül iki bin yirmi altı döneminde hava sıcaklığı yirmi iki virgül altı dereceden on altı virgül kırk bir dereceye düştü. " +
      "Elektrik tüketimi elli dokuz bin altı yüz kırk beş virgül doksan üç kilovatsaat.";
    const energy = "Verisi bulunan son dönem Haziran iki bin yirmi altı: Future Gen Ana Elektrik Sayacı: elli dokuz bin altı yüz kırk beş virgül doksan üç kilovatsaat.";
    expect(splitWidgetTtsText(energy).join(" ")).toBe(energy);
    const chunks = splitWidgetTtsText(text);
    expect(chunks.join(" ")).toBe(text);
    for (const quantity of ["yirmi iki virgül altı dereceden", "on altı virgül kırk bir dereceye", "elli dokuz bin altı yüz kırk beş virgül doksan üç kilovatsaat"]) {
      expect(chunks.some((chunk) => chunk.includes(quantity))).toBe(true);
    }
    expect(chunks.every((chunk) => chunk.length <= WIDGET_TTS_CHUNK_MAX_CHARS)).toBe(true);
  });

  it("pauses at clause boundaries and keeps spoken dates and clock times whole", () => {
    // Long Turkish replies captured from live speech, previously split mid-phrase.
    const window = "Bu bulgu on sekiz Ekim iki bin yirmi üç saat yirmi üç on bir ile on yedi Ekim iki bin yirmi altı saat " +
      "yirmi üç on bir arasındaki veri kullanılarak değerlendirildi.";
    const findings = "dokuz etkin bulgu var: Birinci bulgu, orta önem düzeyinde: Tesis Toplam Elektrik Tüketimi kaynağında gecikme algılandı.";
    for (const text of [window, findings]) {
      const chunks = splitWidgetTtsText(text);
      expect(chunks.join(" ")).toBe(text);
      expect(chunks.every((chunk) => chunk.length <= WIDGET_TTS_CHUNK_MAX_CHARS)).toBe(true);
    }
    const windowChunks = splitWidgetTtsText(window);
    for (const moment of ["on sekiz Ekim iki bin yirmi üç saat yirmi üç on bir", "on yedi Ekim iki bin yirmi altı saat yirmi üç on bir"]) {
      expect(windowChunks.some((chunk) => chunk.includes(moment))).toBe(true);
    }
    expect(splitWidgetTtsText(findings).some((chunk) => chunk.includes("kaynağında gecikme algılandı"))).toBe(true);
    expect(splitWidgetTtsText(findings)[0].endsWith(":") || splitWidgetTtsText(findings)[0].endsWith(",")).toBe(true);
  });

  it("resolves the widget TTS endpoint from the configured AVAROS URL", () => {
    expect(resolveServerTtsUrl("https://avaros.reneryo.com/base")).toBe(
      "https://avaros.reneryo.com/voice/tts",
    );
  });
});
