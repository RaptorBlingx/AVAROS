import { describe, expect, it } from "vitest";

import {
  detectWidgetLanguage,
  normalizeWidgetLanguage,
  responseLanguage,
} from "./language";

describe("widget conversation language", () => {
  it("detects Turkish and English switches from the current utterance", () => {
    expect(detectWidgetLanguage("Bu bulgu neden oluştu?", "en-US")).toBe("tr-TR");
    expect(detectWidgetLanguage("Why did this finding trigger?", "tr-TR")).toBe("en-US");
  });

  it("keeps the current locale for language-neutral follow-ups", () => {
    expect(detectWidgetLanguage("Tesis Toplam Üretim Miktarı", "tr-TR")).toBe(
      "tr-TR",
    );
  });

  it("prefers explicit response metadata over the signed initial locale", () => {
    expect(
      responseLanguage(
        {
          data: {
            meta: {
              language: "tr-TR",
              avaros_response: { language: "tr-TR" },
            },
          },
          context: { session: { lang: "en-US" } },
        },
        "en-US",
      ),
    ).toBe("tr-TR");
  });

  it("prefers the updated session locale over the skill's static data locale", () => {
    expect(
      responseLanguage(
        {
          data: { lang: "en-US" },
          context: { session: { lang: "tr-TR" } },
        },
        "en-US",
      ),
    ).toBe("tr-TR");
  });

  it("normalizes supported BCP-47 variants", () => {
    expect(normalizeWidgetLanguage("tr_tr")).toBe("tr-TR");
    expect(normalizeWidgetLanguage("en-gb")).toBe("en-US");
  });
});
