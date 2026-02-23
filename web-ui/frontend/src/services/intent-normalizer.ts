function sanitize(raw: string): string {
  return raw.trim().toLowerCase().replace(/\s+/g, " ");
}

export function normalizeUtteranceForIntent(raw: string): string {
  let text = raw.trim().replace(/[.!?;:]+$/g, "").trim();
  if (!text) return text;
  text = text.replace(/[!?;:]+/g, " ");

  // Common substitutions from STT + typed shorthand.
  text = text.replace(/°/g, " degrees");
  text = text.replace(/\bwhat if (you|u)\b/gi, "what if we");
  text = text.replace(/\btrain\b/gi, "trend");
  text = text.replace(
    /\b(energy|scrap|waste|oee|production)\s+turn\b/gi,
    "$1 trend",
  );
  text = text.replace(/\bturn\s+(graph|chart|data|report)\b/gi, "trend $1");
  text = text.replace(/\bv\s*s\b/gi, "vs");
  text = text.replace(/\bverse us\b/gi, "versus");
  text = text.replace(/\bverses\b/gi, "versus");
  // Frequent STT confusion: "OA" is intended as "OEE".
  text = text.replace(/\bwhat\s+is\s+the\s+oa\b/gi, "what is the oee");
  text = text.replace(/\boa\s+for\b/gi, "oee for");
  text = text.replace(
    /\bwhich uses more energy\b.+\b(vs|versus|or)\b.+/gi,
    "which uses more energy",
  );
  text = text.replace(
    /\bwhich is more efficient\b.+\b(vs|versus|or)\b.+/gi,
    "which is more efficient",
  );
  // Collapse only ambiguous compare phrasings that don't specify
  // "between X and Y". Keep explicit pair utterances intact.
  text = text.replace(
    /\bcompare\b(?![^.]*\bbetween\b).+\b(energy|power)\b.+\b(vs|versus|or)\b.+/gi,
    "compare energy",
  );
  text = text.replace(
    /\b(show|display)\s+(scrap|waste)\s+trend\b/gi,
    "$1 $2 rate trend",
  );
  text = text.replace(/\b(scrap|waste)\s+trend\b/gi, "$1 rate trend");
  text = text.replace(
    /\bcheck production on amalie\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production on a money\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production on anomaly\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bcheck production anomal(y|ies)\b/gi,
    "check production anomaly",
  );
  text = text.replace(
    /\bwhat is temperature (increase|increases|increased|raise|raises|raised)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat is temperature (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we decrease temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if temperature (increase|increases|increased|raise|raises|raised)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if we (increase|increases|increased|raise|raises|raised)\s+temperature\s+by\s+([0-9]+(?:\.[0-9]+)?)\b/gi,
    "what if we increase temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if temperature (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+by\s+([0-9]+(?:\.[0-9]+)?)\s*degrees?\b/gi,
    "what if we decrease temperature by $2 degrees",
  );
  text = text.replace(
    /\bwhat if we (decrease|decreases|decreased|reduce|reduces|reduced|lower|lowers|lowered)\s+temperature\s+by\s+([0-9]+(?:\.[0-9]+)?)\b/gi,
    "what if we decrease temperature by $2 degrees",
  );

  // Canonicalize very short MVP commands to routable phrases.
  const compact = sanitize(text);
  if (
    compact === "production anomalies" ||
    compact === "production anomaly" ||
    compact === "check production anomalies" ||
    compact === "check production anomaly" ||
    compact === "show production anomalies" ||
    compact === "show production anomaly"
  ) {
    return "check production anomaly";
  }
  if (compact === "energy trend" || compact === "energy trends") {
    return "show energy trend";
  }
  if (
    compact === "scrap trend" ||
    compact === "scrap trends" ||
    compact === "waste trend" ||
    compact === "waste trends"
  ) {
    return "show scrap rate trend";
  }
  if (
    compact === "show scrap rate trend" ||
    compact === "show waste rate trend"
  ) {
    return "what's the scrap rate trend";
  }
  if (compact === "oee") {
    return "what is the oee";
  }
  if (compact === "oa" || compact === "show oa" || compact === "current oa") {
    return "what is the oee";
  }
  if (
    compact === "show oee" ||
    compact === "current oee" ||
    compact === "oee today"
  ) {
    return "what is the oee";
  }
  if (
    compact === "scrap rate" ||
    compact === "waste rate" ||
    compact === "show scrap rate" ||
    compact === "show waste rate"
  ) {
    return "what's the scrap rate";
  }
  if (compact === "energy per unit" || compact === "power per unit") {
    return "show energy per unit today";
  }
  if (compact === "show energy per unit" || compact === "show power per unit") {
    return "show energy per unit today";
  }
  if (
    compact === "energy comparison" ||
    compact === "compare energy usage" ||
    compact === "compare power usage"
  ) {
    return "compare energy";
  }
  if (compact === "compare energy" || compact === "compare power") {
    return "compare energy";
  }

  return text.replace(/\s+/g, " ").trim().replace(/[.!?]+$/g, "").trim();
}
