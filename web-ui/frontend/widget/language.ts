type BusLanguageMessage = {
  data?: Record<string, unknown>;
  context?: Record<string, unknown>;
};

const TURKISH_WORDS = new Set([
  "bu",
  "bulgu",
  "bulguyu",
  "bulgular",
  "hangi",
  "neden",
  "kanıt",
  "kanit",
  "dönem",
  "donem",
  "göster",
  "goster",
  "listele",
  "metrik",
  "regresyon",
  "sayaç",
  "sayac",
  "eğilim",
  "egilim",
  "peki",
  "dun",
  "bugun",
  "haziran",
  "ocak",
  "subat",
  "mart",
  "nisan",
  "mayis",
  "temmuz",
  "agustos",
  "eylul",
  "ekim",
  "kasim",
  "aralik",
  "ne",
  "kadar",
  "veri",
  "degerlendir",
  "lutfen",
  "incele",
  "kontrol",
  "simdi",
]);

const ENGLISH_WORDS = new Set([
  "this",
  "finding",
  "findings",
  "what",
  "why",
  "which",
  "explain",
  "evidence",
  "period",
  "entity",
  "show",
  "list",
  "trend",
  "regression",
  "meter",
  "metric",
  "i",
  "need",
  "should",
  "review",
  "check",
  "and",
  "yesterday",
  "today",
  "january",
  "february",
  "march",
  "april",
  "may",
  "june",
  "july",
  "august",
  "september",
  "october",
  "november",
  "december",
  "evaluate",
  "please",
  "run",
  "how",
  "did",
  "we",
]);

export function normalizeWidgetLanguage(language: unknown): string {
  const normalized = String(language ?? "")
    .trim()
    .replace("_", "-")
    .toLowerCase();
  if (normalized.startsWith("tr")) return "tr-TR";
  return "en-US";
}

export function detectWidgetLanguage(text: string, fallback: string): string {
  // Locale-neutral casing must not manufacture Turkish ı from English I.
  const normalized = text.normalize("NFKC").toLowerCase().replace(/i\u0307/g, "i");
  const words = normalized.match(/[a-zçğıöşü]+/giu) ?? [];
  const turkishScore = words.filter((word) => TURKISH_WORDS.has(word)).length;
  const englishScore = words.filter((word) => ENGLISH_WORDS.has(word)).length;
  // Clear language words outrank accents in an unchanged Reneryo name.
  if (turkishScore > englishScore) return "tr-TR";
  if (englishScore > turkishScore) return "en-US";
  if (/[çğıöşü]/iu.test(normalized)) return "tr-TR";
  return normalizeWidgetLanguage(fallback);
}

export function responseLanguage(
  message: BusLanguageMessage,
  fallback: string,
): string {
  const data = message.data ?? {};
  const meta = isRecord(data.meta) ? data.meta : {};
  const response = isRecord(meta.avaros_response) ? meta.avaros_response : {};
  const context = message.context ?? {};
  const reneryo = isRecord(context.reneryo_context)
    ? context.reneryo_context
    : {};
  const session = isRecord(context.session) ? context.session : {};
  const candidate =
    response.language ??
    meta.language ??
    data.language ??
    reneryo.language ??
    session.lang ??
    data.lang;
  return normalizeWidgetLanguage(candidate ?? fallback);
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}
