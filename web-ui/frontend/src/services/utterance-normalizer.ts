/**
 * Normalize STT utterances for known AVAROS voice-query variants.
 *
 * Handles common ASR artifacts such as spaced OEE tokens and
 * spoken line numbers ("line one" -> "line 1").
 */

const LINE_NUMBER_WORDS: Record<string, string> = {
  zero: "0",
  one: "1",
  two: "2",
  three: "3",
  four: "4",
  five: "5",
  six: "6",
  seven: "7",
  eight: "8",
  nine: "9",
  ten: "10",
};

export function normalizeUtterance(raw: string): string {
  let normalized = raw.toLowerCase().trim();

  normalized = normalized.replace(/\bo\s*e\s*e\b/g, "oee");
  normalized = normalized.replace(/\bo\s*o\s*e\b/g, "oee");
  normalized = normalized.replace(/\bo\s*e\b/g, "oee");

  normalized = normalized.replace(
    /\bline\s+(zero|one|two|three|four|five|six|seven|eight|nine|ten)\b/g,
    (_, word: string) => `line ${LINE_NUMBER_WORDS[word]}`,
  );

  normalized = normalized.replace(/\s+/g, " ").trim();
  return normalized;
}
