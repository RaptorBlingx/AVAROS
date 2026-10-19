/**
 * Clean transport whitespace without interpreting the user's request.
 *
 * Shared by typed and voice inputs. Intent, terminology and defaults belong
 * to backend resolution: client rewrites can erase entities, periods or
 * negation, and an apparent STT typo can be a valid industrial term.
 */
export function normalizeUtteranceForIntent(raw: string): string {
  return raw.trim().replace(/\s+/g, " ");
}
