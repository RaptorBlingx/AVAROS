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


it.each([
  ["I need energy consumption for yesterday.", "tr-TR", "en-US"],
  ["What should I check in the factory data?", "tr-TR", "en-US"],
  ["What should I review next?", "tr-TR", "en-US"],
  ["Peki Haziran?", "en-US", "tr-TR"],
  ["Peki dun?", "en-US", "tr-TR"],
  ["And June?", "tr-TR", "en-US"],
  ["And yesterday?", "tr-TR", "en-US"],
  ["Show Tesis Toplam Üretim Miktarı", "tr-TR", "en-US"],
  ["İlgili metriği göster", "en-US", "tr-TR"],
  ["123", "tr-TR", "tr-TR"],
  ["Line-10 OEE", "en-US", "en-US"],
])("detects %s without changing its text", (text, fallback, expected) => {
  expect(detectWidgetLanguage(text, fallback)).toBe(expected);
});

it("keeps a current-turn switch across neutral follow-ups and response metadata", () => {
  let language = "en-US";
  for (const [text, expected] of [
    ["Peki Haziran?", "tr-TR"], ["2020", "tr-TR"],
    ["And production for the same period?", "en-US"], ["Line-10", "en-US"],
  ]) {
    language = detectWidgetLanguage(text, language);
    expect(language).toBe(expected);
    language = responseLanguage({data: {meta: {avaros_response: {language}}}}, language);
    expect(language).toBe(expected);
  }
});

it.each([
  ["Bunun sorumlusu kim?", "en-US", "tr-TR"],
  ["Who owns it?", "tr-TR", "en-US"],
  ["Neyi incelemem gerekiyor?", "en-US", "tr-TR"],
  ["How recent is that data?", "tr-TR", "en-US"],
])("keeps D08 paraphrases in their current-turn language: %s", (text, fallback, expected) => {
  expect(detectWidgetLanguage(text, fallback)).toBe(expected);
});
