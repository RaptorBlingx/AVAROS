/**
 * Pure guard functions for voice interaction quality filtering.
 *
 * Extracted from VoiceContext to keep the provider focused on
 * orchestration while these remain independently testable.
 */

/** Return true when STT result matches the last TTS utterance (acoustic feedback loop). */
export function isOwnPromptEcho(
  transcript: string,
  lastTtsUtterance: string,
): boolean {
  if (!lastTtsUtterance) return false;
  const n = transcript.trim().toLowerCase().replace(/\s+/g, " ");
  const ref = lastTtsUtterance.trim().toLowerCase().replace(/\s+/g, " ");
  if (!n || !ref) return false;
  const allowContainsMatch = ref.length >= 12;
  // Exact match, prefix match, or substring containment (accounts for STT
  // mis-hearing a fragment of the TTS prompt).
  return (
    n === ref ||
    n.startsWith(ref) ||
    ref.startsWith(n) ||
    (allowContainsMatch && n.includes(ref))
  );
}

/** Return true when STT transcript is too short or garbled to be a real command. */
export function isLikelyNoiseUtterance(raw: string): boolean {
  const text = raw.trim().toLowerCase();
  if (!text) return true;
  if (text.length <= 2) return true;
  if (!/[a-z]/.test(text)) return true;

  // Low-signal gibberish guard (e.g. "asdasd", "qweqwe").
  const compact = text.replace(/\s+/g, "");
  const uniqueChars = new Set(compact).size;
  if (compact.length >= 6 && uniqueChars <= 3) return true;

  return false;
}

/** Return true when transcript is a known incomplete command prefix. */
export function isIncompleteIntentText(raw: string): boolean {
  const text = raw.trim().toLowerCase().replace(/\s+/g, " ");
  if (!text) return true;

  const exactIncomplete = new Set([
    "what if",
    "show",
    "show me",
    "what is",
    "what's",
    "check",
  ]);
  if (exactIncomplete.has(text)) return true;

  const hasAmount =
    /\d|\b(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\b/.test(
      text,
    );
  if (text.startsWith("what if") && !hasAmount) return true;
  return false;
}
