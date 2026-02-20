// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import { normalizeUtterance } from "../utterance-normalizer";

describe("normalizeUtterance", () => {
  it("normalizes spaced oee variants", () => {
    expect(normalizeUtterance("what is o e e for line one"))
      .toBe("what is oee for line 1");
    expect(normalizeUtterance("what is o o e for line two"))
      .toBe("what is oee for line 2");
    expect(normalizeUtterance("show oe now"))
      .toBe("show oee now");
  });

  it("normalizes line number words", () => {
    expect(normalizeUtterance("compare energy between line one and line two"))
      .toBe("compare energy between line 1 and line 2");
  });

  it("keeps valid utterances stable besides casing", () => {
    expect(normalizeUtterance("Compare energy between Line 1 and line 2"))
      .toBe("compare energy between line 1 and line 2");
  });
});
