"""Bounded parsing and wording for a conversational MDSP finding collection."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from skill.domain.reneryo_models import MdspEvaluation, MdspFinding, MdspFindingList
from skill.services.conversation_state import DialogueState
from skill.services.language import is_turkish

_STATUSES = {"ACTIVE", "RESOLVED"}
_SEVERITIES = {"HIGH", "MEDIUM", "LOW", "INFO"}
_DOMAINS = {"METERS", "METRICS", "TRENDS", "SEU", "REGRESSION"}


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
    collection_followup = state.operation in {"findings", "evaluation"} and any(
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
    return explicit or collection_followup or (
        state.operation in {"findings", "evaluation"} and filter_cue
    )


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
    ordinals = {
        "first": 0,
        "1st": 0,
        "one": 0,
        "second": 1,
        "2nd": 1,
        "two": 1,
        "third": 2,
        "3rd": 2,
        "three": 2,
        "fourth": 3,
        "4th": 3,
        "four": 3,
        "ilk": 0,
        "ilkini": 0,
        "birinci": 0,
        "birincisini": 0,
        "ikinci": 1,
        "ikincisini": 1,
        "ucuncu": 2,
        "ucuncuyu": 2,
        "üçüncü": 2,
        "üçüncüyü": 2,
        "dorduncu": 3,
        "dorduncuyu": 3,
        "dördüncü": 3,
        "dördüncüyü": 3,
    }
    for word, index in ordinals.items():
        if re.search(rf"(?<!\w){re.escape(word)}(?!\w)", text):
            return index if index < len(state.finding_ids) else None
    match = re.search(r"\b(?:number|no|numara|numarali|numaralı)\s+(\d+)\b", text)
    if match:
        index = int(match.group(1)) - 1
        return index if 0 <= index < len(state.finding_ids) else None
    return None


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
    """Make clear that MDSP ran the analysis before AVAROS narrated it."""
    collection = collection_headline(result, filters, language)
    if is_turkish(language):
        return (
            f"MDSP güncel Reneryo verileri için yeni değerlendirmeyi tamamladı. "
            f"{evaluation.evaluated_resource_count} kaynak değerlendirildi; "
            f"{evaluation.active_finding_count} etkin bulgu var ve "
            f"{evaluation.resolved_finding_count} bulgu çözüldü. {collection}"
        )
    return (
        f"MDSP completed a fresh evaluation of current Reneryo data. "
        f"It evaluated {evaluation.evaluated_resource_count} resources, found "
        f"{evaluation.active_finding_count} active findings, and resolved "
        f"{evaluation.resolved_finding_count}. {collection}"
    )


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
