// @vitest-environment jsdom

import { describe, expect, it } from "vitest";

import { normalizeUtteranceForIntent } from "../intent-normalizer";

describe("normalizeUtteranceForIntent", () => {
  it("normalizes common energy typo in trend commands", () => {
    expect(normalizeUtteranceForIntent("show snergy trend today"))
      .toBe("show energy trend today");
  });

  it("preserves explicit compare pairs", () => {
    expect(normalizeUtteranceForIntent("compare energy between line 1 and line 2"))
      .toBe("compare energy between line 1 and line 2");
  });

  it("normalizes train->trend typo", () => {
    expect(normalizeUtteranceForIntent("show energy train today"))
      .toBe("show energy trend today");
  });
});

