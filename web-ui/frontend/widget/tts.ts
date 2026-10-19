export const WIDGET_TTS_CHUNK_MAX_CHARS = 105;

export function resolveServerTtsUrl(avarosUrl: string): string {
  try {
    return new URL("/voice/tts", avarosUrl).toString();
  } catch {
    return "/voice/tts";
  }
}

export function splitWidgetTtsText(
  text: string,
  maxChars = WIDGET_TTS_CHUNK_MAX_CHARS,
): string[] {
  const normalized = text.replace(/\s+/g, " ").trim();
  if (!normalized) return [];
  if (normalized.length <= maxChars) return [normalized];

  const chunks: string[] = [];
  let current = "";

  for (const sentence of splitIntoSentences(normalized)) {
    if (!sentence) continue;
    if (sentence.length > maxChars) {
      if (current) {
        chunks.push(current);
        current = "";
      }
      chunks.push(...splitLongSentence(sentence, maxChars));
      continue;
    }

    const next = current ? `${current} ${sentence}` : sentence;
    if (next.length > maxChars && current) {
      chunks.push(current);
      current = sentence;
    } else {
      current = next;
    }
  }

  if (current) chunks.push(current);
  return chunks;
}

function splitLongSentence(sentence: string, maxChars: number): string[] {
  const chunks: string[] = [];
  let current = "";
  // Keep a spoken number and its unit in the same playback clip.
  const numberWord = "(?:sıfır|bir|iki|üç|dört|beş|altı|yedi|sekiz|dokuz|on|yirmi|otuz|kırk|elli|altmış|yetmiş|seksen|doksan|yüz|bin|milyon|milyar|trilyon|virgül|eksi|artı|yüzde)";
  const unit = "(?:derece(?:den|ye|lik)?|kilovatsaat|megavatsaat|kilovat|megavat|metreküp|kilogram|saat|dakika|saniye|gün)";
  const atoms = sentence.match(new RegExp(
    `(?<![\\p{L}\\p{N}_-])${numberWord}(?: ${numberWord})*(?: ${unit})?(?![\\p{L}\\p{N}_-])[.,;:!?]?|\\S+`, "gu",
  )) ?? [];
  const boundedAtoms = atoms.flatMap((atom) => atom.length > maxChars ? atom.split(/\s+/) : [atom]);
  for (const word of boundedAtoms) {
    const next = current ? `${current} ${word}` : word;
    if (next.length > maxChars && current) {
      chunks.push(current);
      current = word;
    } else {
      current = next;
    }
  }
  if (current) chunks.push(current);
  return chunks;
}

function splitIntoSentences(text: string): string[] {
  const sentences: string[] = [];
  let start = 0;

  for (let index = 0; index < text.length; index += 1) {
    const char = text[index];
    if (!".!?;".includes(char)) continue;

    const prev = text[index - 1] ?? "";
    const next = text[index + 1] ?? "";
    if (char === "." && /\d/.test(prev) && /\d/.test(next)) continue;
    if (next && !/\s/.test(next)) continue;

    const sentence = text.slice(start, index + 1).trim();
    if (sentence) sentences.push(sentence);
    start = index + 1;
    while (start < text.length && /\s/.test(text[start])) start += 1;
    index = start - 1;
  }

  const rest = text.slice(start).trim();
  if (rest) sentences.push(rest);
  return sentences.length > 0 ? sentences : [text];
}
