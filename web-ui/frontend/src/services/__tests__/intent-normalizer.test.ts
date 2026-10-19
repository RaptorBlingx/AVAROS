import { describe, expect, it } from "vitest";

import { normalizeUtteranceForIntent } from "../intent-normalizer";

describe("normalizeUtteranceForIntent", () => {
  it.each([
    "Compare energy consumption of boiler 1 vs boiler 2 yesterday",
    "Show compressor train energy consumption yesterday",
    "Which uses more energy, boiler 1 versus boiler 2 last month?",
    "Which is more efficient, compressor train A or compressor train B today?",
    "compare energy between line 1 and line 2",
    "Do not compare energy for boiler 1 vs boiler 2; show metrics instead",
    "Don't show findings; show metrics instead!",
    "Show energy for Boiler-A on 2026-10-12 between 08:30 and 09:45",
    "Show boiler 1 temperature above 80°C, not boiler 2",
    "Dün kazan 1 ile kazan 2 enerji tüketimini karşılaştır; bulguları gösterme",
    "show energy train today",
    "show snergy trend today",
    "Turn compressor train A off; do not show its trend",
    "Show waste trend for OA production yesterday",
    "Compare verses used by line 1 vs line 2",
    "oee today",
    "energy per unit",
    "power per unit",
    "show waste rate trend",
    "energy trend",
    "scrap trend",
    "production anomalies",
    "oee",
    "compare energy usage",
  ])("preserves the complete request: %s", (request) => {
    expect(normalizeUtteranceForIntent(request)).toBe(request);
    expect(normalizeUtteranceForIntent(normalizeUtteranceForIntent(request)))
      .toBe(request);
  });

  it("only trims and collapses whitespace", () => {
    expect(normalizeUtteranceForIntent("  Compare\tboiler 1\nvs  boiler 2 yesterday?  "))
      .toBe("Compare boiler 1 vs boiler 2 yesterday?");
  });

  it.each(["", " \t\n "])("handles empty input", (request) => {
    expect(normalizeUtteranceForIntent(request)).toBe("");
  });
});
