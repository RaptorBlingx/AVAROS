import { describe, expect, it } from "vitest";
import {
  isIncompleteIntentText,
  isLikelyNoiseUtterance,
  isOwnPromptEcho,
} from "../voice-guards";

describe("isOwnPromptEcho", () => {
  it("detects exact match as echo", () => {
    expect(isOwnPromptEcho("How can I help you?", "How can I help you?")).toBe(
      true,
    );
  });

  it("detects case-insensitive match", () => {
    expect(isOwnPromptEcho("how can i help you", "How can I help you?")).toBe(
      true,
    );
  });

  it("detects prefix match as echo", () => {
    expect(isOwnPromptEcho("How can I", "How can I help you?")).toBe(true);
  });

  it("returns false for unrelated text", () => {
    expect(isOwnPromptEcho("show energy trend", "How can I help you?")).toBe(
      false,
    );
  });

  it("returns false when no last utterance", () => {
    expect(isOwnPromptEcho("hello", "")).toBe(false);
  });
});

describe("isLikelyNoiseUtterance", () => {
  it("rejects empty string", () => {
    expect(isLikelyNoiseUtterance("")).toBe(true);
  });

  it("rejects very short text", () => {
    expect(isLikelyNoiseUtterance("ab")).toBe(true);
  });

  it("rejects non-alpha gibberish", () => {
    expect(isLikelyNoiseUtterance("123")).toBe(true);
  });

  it("rejects repetitive gibberish", () => {
    expect(isLikelyNoiseUtterance("ababab")).toBe(true);
  });

  it("accepts valid command", () => {
    expect(isLikelyNoiseUtterance("show energy trend")).toBe(false);
  });
});

describe("isIncompleteIntentText", () => {
  it("detects bare what if as incomplete", () => {
    expect(isIncompleteIntentText("what if")).toBe(true);
  });

  it("detects bare show as incomplete", () => {
    expect(isIncompleteIntentText("show")).toBe(true);
  });

  it("accepts what if with amount", () => {
    expect(
      isIncompleteIntentText("what if we increase temperature by 5 degrees"),
    ).toBe(false);
  });

  it("accepts full command", () => {
    expect(isIncompleteIntentText("show energy trend")).toBe(false);
  });
});
