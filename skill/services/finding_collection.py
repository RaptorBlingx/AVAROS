"""Bounded parsing and wording for a conversational MDSP finding collection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from skill.domain.reneryo_models import MdspEvaluation, MdspFindingList
from skill.services.conversation_state import DialogueState
from skill.services.language import is_turkish

_STATUSES = {"ACTIVE", "RESOLVED"}
_SEVERITIES = {"HIGH", "MEDIUM", "LOW", "INFO"}
_DOMAINS = {"METERS", "METRICS", "TRENDS", "SEU", "REGRESSION"}

# These are deliberately limited to the bounded MDSP collection selector. They
# are not a global spelling-correction dictionary for arbitrary dialogue.
_ORDINALS = {
    "first": 0,
    "1st": 0,
    "second": 1,
    "2nd": 1,
    "third": 2,
    "3rd": 2,
    "fourth": 3,
    "4th": 3,
    "ilk": 0,
    "ilki": 0,
    "ilkini": 0,
    "birinci": 0,
    "birincisi": 0,
    "birincisini": 0,
    "ikinci": 1,
    "ikincisi": 1,
    "ikincisini": 1,
    "ikincini": 1,
    "ucuncu": 2,
    "ucuncusu": 2,
    "ucuncusunu": 2,
    "ucuncuyu": 2,
    "dorduncu": 3,
    "dorduncusu": 3,
    "dorduncusunu": 3,
    "dorduncuyu": 3,
}
_CARDINAL_ORDINALS = {"one": 0, "two": 1, "three": 2, "four": 3}
_SELECTION_CUES = {
    "explain",
    "tell",
    "show",
    "detail",
    "about",
    "acikla",
    "acıkla",
    "anlat",
    "goster",
    "detay",
}


@dataclass(frozen=True)
class FindingFilters:
    """MDSP-supported filters; empty values deliberately inherit prior context."""

    status: str = "ACTIVE"
    severity: str = ""
    domain: str = ""

    def normalized(self) -> FindingFilters:
        return FindingFilters(
            status=self.status.upper() if self.status.upper() in _STATUSES else "ACTIVE",
            severity=self.severity.upper() if self.severity.upper() in _SEVERITIES else "",
            domain=self.domain.upper() if self.domain.upper() in _DOMAINS else "",
        )


def is_evaluation_request(text: str) -> bool:
    """Recognize a request to run MDSP, not merely read existing findings."""
    text = _normalized_text(text)
    evaluation_verbs = (
        "analy",
        "evaluate",
        "assessment",
        "assess ",
        "run a check",
        "check current",
        "degerlendir",
        "değerlendir",
        "analiz",
        "incele",
        "kontrol et",
    )
    data_cues = (
        "data",
        "current",
        "now",
        "findings",
        "finding",
        "attention",
        "reneryo",
        "veri",
        "guncel",
        "güncel",
        "simdi",
        "şimdi",
        "bulgu",
        "dikkat",
    )
    return any(cue in text for cue in evaluation_verbs) and any(
        cue in text for cue in data_cues
    )


def is_collection_request(text: str, state: DialogueState) -> bool:
    """Identify inventory, filtering, and pronoun follow-ups without text memory."""
    text = _normalized_text(text)
    finding_reference = any(
        cue in text
        for cue in (
            "finding",
            "findings",
            "decision support",
            "alert",
            "alerts",
            "issue",
            "issues",
            "bulgu",
            "bulgular",
            "karar destek",
            "uyari",
            "uyarı",
            "uyarilar",
            "uyarılar",
            "sorun",
            "sorunlar",
        )
    )
    inventory_cue = any(
        cue in text
        for cue in (
            "list",
            "show",
            "all ",
            "what ",
            "which ",
            "how many",
            "count",
            "active",
            "unresolved",
            "resolved",
            "high",
            "medium",
            "low",
            "regression",
            "liste",
            "goster",
            "göster",
            "neler",
            "kac ",
            "kaç ",
            "aktif",
            "cozul",
            "çözül",
            "yüksek",
            "orta",
            "düşük",
            "regresyon",
        )
    )
    explicit = finding_reference and (
        inventory_cue
        or text.strip()
        in {"finding", "findings", "bulgu", "bulgular", "uyari", "uyarı"}
    )
    collection_context = state.operation in {"findings", "evaluation"} or (
        state.selected_finding_from_collection and bool(state.finding_ids)
    )
    collection_followup = collection_context and any(
        cue in text
        for cue in (
            "list",
            "show",
            "them",
            "those",
            "ones",
            "only",
            "any ",
            "liste",
            "goster",
            "göster",
            "bunlari",
            "bunları",
            "onlari",
            "onları",
            "sadece",
            "var mi",
            "var mı",
        )
    )
    filter_cue = any(
        cue in text
        for cue in (
            "active",
            "unresolved",
            "resolved",
            "high",
            "medium",
            "low",
            "regression",
            "metrics",
            "aktif",
            "cozulmemis",
            "çözülmemiş",
            "cozuldu",
            "çözüldü",
            "yüksek",
            "orta",
            "düşük",
            "regresyon",
            "metrik",
        )
    )
    return explicit or collection_followup or (collection_context and filter_cue)


def filters_for(text: str, state: DialogueState) -> FindingFilters:
    """Apply explicit EN/TR filter language over bounded prior collection state."""
    text = _normalized_text(text)
    prior = FindingFilters(
        status=state.finding_status or "ACTIVE",
        severity=state.finding_severity,
        domain=state.finding_domain,
    ).normalized()
    status, severity, domain = prior.status, prior.severity, prior.domain

    if _has(text, "resolved", "cozuldu", "çözüldü", "cozulmus", "çözülmüş"):
        status = "RESOLVED"
    elif _has(text, "active", "unresolved", "open", "aktif", "cozulmemis", "çözülmemiş", "acik", "açık"):
        status = "ACTIVE"

    if _has(text, "high", "yüksek"):
        severity = "HIGH"
    elif _has(text, "medium", "orta"):
        severity = "MEDIUM"
    elif _has(text, "low", "düşük"):
        severity = "LOW"
    elif _has(text, "info", "bilgi"):
        severity = "INFO"

    if _has(text, "regression", "regresyon"):
        domain = "REGRESSION"
    elif _has(text, "metric", "metrics", "metrik", "metrikler"):
        domain = "METRICS"
    elif _has(text, "meter", "meters", "sayac", "sayaç"):
        domain = "METERS"
    elif _has(text, "trend", "trends", "egilim", "eğilim"):
        domain = "TRENDS"
    elif _has(text, "seu", "oet", "öet"):
        domain = "SEU"

    return FindingFilters(status=status, severity=severity, domain=domain).normalized()


def selection_index(text: str, state: DialogueState) -> int | None:
    """Return a zero-based ordinal only for the current bounded result collection."""
    text = _normalized_text(text)
    if not state.finding_ids:
        return None
    for word, index in _ORDINALS.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
            return index if index < len(state.finding_ids) else None
    match = re.search(r"\b(?:number|no|numara|numarali|numaralı)\s+(\d+)\b", text)
    if match:
        index = int(match.group(1)) - 1
        return index if 0 <= index < len(state.finding_ids) else None
    # ASR occasionally drops or substitutes a single ordinal character (for
    # example, a Turkish possessive ending). Permit that only with an active,
    # organization-scoped collection and an explicit selection/explanation
    # cue. This cannot select an arbitrary finding ID or autocorrect general
    # conversation outside the collection context.
    words = re.findall(r"\w+", text)
    if not any(word in _SELECTION_CUES for word in words):
        return None
    for spoken in words:
        for ordinal, index in _ORDINALS.items():
            if len(ordinal) >= 4 and _edit_distance_at_most_one(spoken, ordinal):
                return index if index < len(state.finding_ids) else None
    for word, index in _CARDINAL_ORDINALS.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
            return index if index < len(state.finding_ids) else None
    return None


def _edit_distance_at_most_one(left: str, right: str) -> bool:
    """Return whether two short selector tokens differ by at most one edit."""
    if left == right:
        return True
    if abs(len(left) - len(right)) > 1:
        return False
    if len(left) == len(right):
        return sum(a != b for a, b in zip(left, right, strict=True)) <= 1
    shorter, longer = sorted((left, right), key=len)
    short_index = long_index = edits = 0
    while short_index < len(shorter) and long_index < len(longer):
        if shorter[short_index] == longer[long_index]:
            short_index += 1
            long_index += 1
            continue
        edits += 1
        if edits > 1:
            return False
        long_index += 1
    return True


def collection_headline(
    result: MdspFindingList, filters: FindingFilters, language: str
) -> str:
    """Narrate the actual filtered records, not only an aggregate count."""
    rows = list(result.findings)
    filter_text = _filter_label(filters, language)
    if not rows:
        return (
            f"{filter_text} bulgu yok."
            if is_turkish(language)
            else f"There are no {filter_text.lower()} findings."
        )
    items = "; ".join(
        f"{index}. {_localized_severity(row.severity, language)} — {row.title.for_language(language)}"
        for index, row in enumerate(rows, start=1)
    )
    if is_turkish(language):
        return (
            f"{len(rows)} {filter_text} bulgu var: {items}. "
            "Birini açıklamam için örneğin “ilkini açıkla” diyebilirsiniz."
        )
    return (
        f"There are {len(rows)} {filter_text.lower()} findings: {items}. "
        "You can say, for example, “Explain the first one.”"
    )


def evaluation_headline(
    evaluation: MdspEvaluation,
    result: MdspFindingList,
    filters: FindingFilters,
    language: str,
) -> str:
    """Narrate a completed evaluation without duplicating a later item list."""
    assessment_summary = _assessment_summary(result, language)
    if is_turkish(language):
        return (
            f"MDSP güncel Reneryo verileri için değerlendirmeyi tamamladı. "
            f"{evaluation.evaluated_resource_count} kaynak değerlendirildi; "
            f"{evaluation.active_finding_count} etkin bulgu var ve "
            f"{evaluation.resolved_finding_count} bulgu çözüldü. {assessment_summary} "
            "Tüm başlıkları duymak için “bunları listele” veya öncelikli olanlara "
            "odaklanmak için “orta önem seviyesindekileri göster” diyebilirsiniz."
        )
    return (
        f"MDSP completed a fresh evaluation of current Reneryo data. "
        f"It evaluated {evaluation.evaluated_resource_count} resources, found "
        f"{evaluation.active_finding_count} active findings, and resolved "
        f"{evaluation.resolved_finding_count}. {assessment_summary} "
        "Say “List them” for every title, or “Show the medium ones” to focus on "
        "the priority items."
    )


def _assessment_summary(result: MdspFindingList, language: str) -> str:
    """Describe priority and affected domains without enumerating finding titles."""
    counts = {key.upper(): value for key, value in result.severity_counts.items()}
    high, medium, low = (counts.get(level, 0) for level in ("HIGH", "MEDIUM", "LOW"))
    domains = _domain_labels(result, language)
    if is_turkish(language):
        mix = f"Önem düzeyi dağılımı: {high} yüksek, {medium} orta ve {low} düşük."
        priority = "Yüksek" if high else "Orta" if medium else "Düşük"
        return f"{mix} {priority} öncelikli bulgular şu alanlarla ilgilidir: {domains}."
    mix = f"Severity mix: {high} high, {medium} medium, and {low} low."
    priority = "high" if high else "medium" if medium else "low"
    return f"{mix} The {priority}-priority findings cover {domains}."


def _domain_labels(result: MdspFindingList, language: str) -> str:
    """Use MDSP-returned domains only; do not infer a business category."""
    labels = {
        "METERS": ("meters", "sayaç"),
        "METRICS": ("metrics", "metrik"),
        "TRENDS": ("trends", "eğilim"),
        "SEU": ("significant energy uses", "önemli enerji kullanımı"),
        "REGRESSION": ("regression", "regresyon"),
    }
    values = sorted(
        {
            labels[finding.domain.upper()][0 if not is_turkish(language) else 1]
            for finding in result.findings
            if finding.domain.upper() in labels
        }
    )
    if not values:
        return "the available data" if not is_turkish(language) else "mevcut veri alanlarını"
    if len(values) == 1:
        return values[0]
    conjunction = " ve " if is_turkish(language) else " and "
    return ", ".join(values[:-1]) + conjunction + values[-1]


def _filter_label(filters: FindingFilters, language: str) -> str:
    parts = []
    if filters.status == "RESOLVED":
        parts.append("çözülmüş" if is_turkish(language) else "resolved")
    else:
        parts.append("etkin" if is_turkish(language) else "active")
    if filters.severity:
        labels = {
            "HIGH": ("yüksek", "high"),
            "MEDIUM": ("orta", "medium"),
            "LOW": ("düşük", "low"),
            "INFO": ("bilgi", "informational"),
        }
        parts.append(labels[filters.severity][0 if is_turkish(language) else 1])
    if filters.domain:
        labels = {
            "METERS": ("sayaç", "meter"),
            "METRICS": ("metrik", "metric"),
            "TRENDS": ("eğilim", "trend"),
            "SEU": ("ÖET", "significant energy use"),
            "REGRESSION": ("regresyon", "regression"),
        }
        parts.append(labels[filters.domain][0 if is_turkish(language) else 1])
    return " ".join(parts)


def _localized_severity(value: str, language: str) -> str:
    labels = {
        "HIGH": ("Yüksek", "High"),
        "MEDIUM": ("Orta", "Medium"),
        "LOW": ("Düşük", "Low"),
        "INFO": ("Bilgi", "Info"),
    }
    return labels.get(value.upper(), (value, value))[0 if is_turkish(language) else 1]


def _has(text: str, *values: str) -> bool:
    return any(re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text) for value in values)


def _normalized_text(text: str) -> str:
    """Case-fold Turkish reliably, including capital dotted İ from STT output."""
    folded = unicodedata.normalize("NFKD", text.casefold())
    return "".join(character for character in folded if not unicodedata.combining(character))
