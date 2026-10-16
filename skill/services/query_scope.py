"""Bounded scope cues used to keep factory answers out of asset requests.

These cues identify a requested scope; only the current asset registry can
resolve it. They never infer an equipment ID or a metric binding.
"""

import re

from skill.services.language import normalize_phrase
from skill.services.period_resolution import _MONTH_NAMES
from skill.services.quantities import normalize_quantity_expressions


_COMPARISON = re.compile(
    r"\b(?:compare|comparison|versus|vs|difference between|"
    r"which uses more|which is more efficient|stack up against|"
    r"which (?:line|asset|meter) (?:had|has|uses|used|consumed) "
    r"(?:better|higher|lower|more|less)|"
    r"(?:mi|mı|mu|mü) yoksa .+? (?:mi|mı|mu|mü) daha (?:iyi|yüksek|düşük|fazla|az)|"
    r"karşılaştır\w*|karsilastir\w*|kıyasla\w*|kiyasla\w*)\b"
)
_EQUIPMENT = re.compile(
    r"\b(?:(?:boiler|compressor|turbine|pump|oven|machine|"
    r"line|department|workshop)(?:s|\d+)?|equipment|plant\s+(?:[a-z]|\d+)\b|"
    r"kazan\w*|kompresör\w*|kompresor\w*|pompa\w*|türbin\w*|turbin\w*|"
    r"fırın\w*|firin\w*|makine\w*|ekipman\w*|hat\w*|bölüm\w*|bolum\w*)\b|"
    r"\b(?:meters?|resources?|sayaç|sayac)\s+"
    r"(?!(?:for|of|in|on|at|readings?|consumption|history|data|list|inventory|today|yesterday|last|"
    r"record\w*|measure\w*|monitor\w*|track\w*|are|is|do|have|can|available|configured|"
    r"değer\w*|deger\w*|okuma|tüket\w*|tuket\w*|veri\w*|geçmiş|gecmis|için|icin|bu|son|dün|bugün)\b)[\w-]+"
)
_MEASUREMENT = re.compile(
    r"\b(?:electric\w*|energy|production|output|consum\w*|trend|reading|"
    r"temperature|humidity|oee|scrap|waste|throughput|measurement|metrics?|metrik\w*|"
    r"show|display|report|what|how|values?|review|inspect|incele\w*|kontrol|göster\w*|goster\w*|"
    r"elektr\w*|enerji|üret\w*|uret\w*|tüket\w*|tuket\w*|"
    r"eğilim|egilim|sıcaklık|sicaklik|nem)\b"
)
_COMPARISON_ENTITY = re.compile(
    r"(?:\b(?:between|vs|versus|against|with|and|or|ile|ve)\s+|"
    r",\s*(?:(?:and|or|ile|ve)\s+)?)([\w-]+)"
)
_NON_ENTITY = re.compile(
    rf"^(?:{_MONTH_NAMES}|today|yesterday|last|past|previous|this|that|same|"
    r"current|latest|now|whole|entire|factory|period|data|history|readings?|"
    r"electricity|energy|production|output|temperature|humidity|metrics?|meters?|"
    r"oee|throughput|scrap|waste|units?|pieces?|each|per|reneryo|what|that|this|it|"
    r"configured-asset|measurement|"
    r"bugün|dün|bu|geçen|son|elektrik|enerji|üretim|uretim|dönem|donem)$"
)


def is_comparison_request(utterance: str) -> bool:
    text = normalize_phrase(utterance)
    # Capability questions describe operations rather than requesting one.
    if re.search(r"\b(?:what can|capabilities|ne yapabil|neler yapabil)\w*", text):
        return False
    return bool(_COMPARISON.search(text))


def is_negated_comparison(utterance: str) -> bool:
    if not is_comparison_request(utterance):
        return False
    # A negated operation or excluded entity needs clarification rather than
    # a comparison over every mentioned registry asset.
    return bool(re.search(
        r"\b(?:not|never|don t|no(?!\s+\d)|değil|degil|"
        r"karşılaştırma\w*|karsilastirma\w*|kıyaslama\w*|kiyaslama\w*)\b",
        normalize_phrase(utterance),
    ))


def asset_label_pattern(label: str) -> str:
    """Match a full registry label, preserving established space/dash forms."""
    words = normalize_phrase(label).replace("-", " ").split()
    if not words:
        return r"(?!)"
    phrase = r"[\s-]+".join(re.escape(word) for word in words)
    if len(words) == 2 and words[0] in {"line", "hat"} and words[1].isdigit():
        # Localize the equipment type cue, never the configured identifier.
        phrase = rf"(?:line|hat)[\s-]+{re.escape(words[1])}"
    return rf"(?<![\w-]){phrase}(?![\w-])"


def entity_scope(utterance: str, assets=()) -> tuple[bool, bool]:
    """Return (explicit measurement scope, unresolved equipment cue)."""
    # Commas delimit comparison participants. Keep those boundaries while
    # using the existing Unicode normalization within each source segment.
    text = ", ".join(normalize_phrase(part) for part in utterance.split(","))
    if re.fullmatch(
        r"(?:show|display|list) (?:all |available |configured |the )?"
        r"(?:assets|equipment|meters|metrics|resources)", text,
    ):
        return False, False
    if not (_MEASUREMENT.search(text) or is_comparison_request(text)):
        return False, False
    remaining = text
    matched = False
    labels = sorted({
        normalize_phrase(label)
        for asset in assets
        for label in (asset.asset_id, asset.display_name, *asset.aliases)
        if label
    }, key=len, reverse=True)
    for label in labels:
        remaining, count = re.subn(
            asset_label_pattern(label), " configured-asset ", remaining
        )
        matched = matched or bool(count)
    # OEE's established English/Turkish metric names contain equipment words.
    # They describe the metric, not an additional unresolved asset.
    remaining = re.sub(
        r"\b(?:overall equipment effectiveness|(?:toplam )?ekipman etkinliği)\b",
        "measurement", remaining,
    )
    # An explicit all-asset scope is resolved through the registry, not a
    # factory metric. With an empty registry it remains unavailable.
    remaining, all_assets = re.subn(
        r"\b(?:all lines|every line|all assets|tüm hatlar|bütün hatlar|tüm varlıklar)\b",
        " configured-asset " if assets else "equipment", remaining,
    )
    if is_comparison_request(text):
        remaining = re.sub(r"\bwhich (?:line|asset|meter)\b", "measurement", remaining)
    # Quantity words are not equipment heads (English "by ten percent",
    # Turkish "yüzde on"). Remove verified asset labels first so numbers
    # within source-owned names remain opaque to this local scope check.
    remaining = normalize_quantity_expressions(remaining)
    # Parse the head of a prepositional noun phrase, rather than treating
    # its first adjective/determiner as an asset. Pronouns are not equipment;
    # factory-wide and supported operation nouns are typed domain references.
    qualifiers = re.finditer(
        r"\b(?:for|of|by|at|in|on)\s+"
        r"(?:(?:the|a|an|our|your|their|my|daily|monthly|annual|recorded)\s+)*([\w-]+)|"
        r"\b([\w-]+)\s+(?:s|nın|nin|nun|nün)\b", remaining
    )
    non_asset_head = re.compile(
        r"^(?:me|us|you|them|site|plant|organization|"
        r"regressions?|models?|findings?|assessments?|evaluations?|"
        r"observations?|measurements?|quantities|guidance|evidence)$"
    )
    named_organization = re.search(
        r"\b(?:for|of|in)\s+(?:the\s+)?(?:organization|organisation|tenant)\s+[\w-]+", remaining
    )
    unknown = bool(_EQUIPMENT.search(remaining) or named_organization) or any(
        not re.fullmatch(r"\d[\w-]*", candidate)
        and not _NON_ENTITY.fullmatch(candidate)
        and not non_asset_head.fullmatch(candidate)
        for match in qualifiers
        for candidate in [match.group(1) or match.group(2)]
    )
    if is_comparison_request(text):
        unknown = unknown or any(
            not _NON_ENTITY.fullmatch(match.group(1))
            for match in _COMPARISON_ENTITY.finditer(remaining)
        )
    return matched or bool(all_assets) or unknown, unknown
