"""Deterministic bilingual period extraction for conversational queries."""

from __future__ import annotations

import calendar
import re

from skill.services.language import normalize_phrase

_MONTH_NAMES = (
    "|".join(month.lower() for month in calendar.month_name[1:])
    + r"|ocak|şubat|mart|nisan|mayıs|haziran|temmuz|ağustos|eylül|ekim|kasım|aralık"
)
_NAMED_MONTH_RANGE = re.compile(
    rf"\b(?:{_MONTH_NAMES})(?:\s+\d{{4}})?\s*(?:to|through|and|ile|-)\s*"
    rf"(?:{_MONTH_NAMES})\s+\d{{4}}\b"
)
_NAMED_MONTH = re.compile(rf"\b(?:{_MONTH_NAMES})\s+\d{{4}}\b")

_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), canonical)
    for pattern, canonical in (
        (r"\b(?:previous|prior) calendar month\b", "last month"),
        (r"\b(?:previous|last) month\b", "last month"),
        (r"\bpast month\b", "past month"),
        (r"\b(?:preceding|previous|last|past) four weeks\b", "last 4 weeks"),
        (r"\b(?:last|past) 4 weeks\b", "last 4 weeks"),
        (r"\b(?:last|past) (?:thirty|30) days\b", "last 30 days"),
        (r"\bprevious week\b", "last week"),
        (r"\b(?:last|past) week\b", "last week"),
        (r"\b(?:last|past) (?:two|2) weeks\b", "last 2 weeks"),
        (r"\bthis month\b", "this month"),
        (r"\bthis week\b", "this week"),
        (r"\byesterday\b", "yesterday"),
        (r"\btoday\b", "today"),
        (r"\b(?:right now|latest|current)\b", "latest"),
        (
            r"\bgeçen (?:takvim )?ay(?:ın|ı|a|da|dan|ında|ındaki)?\b",
            "geçen ay",
        ),
        (r"\bson ay(?:ın|ı|a|da|dan)?\b", "son ay"),
        (r"\bson (?:dört|4) hafta(?:yı|ya|daki|da|dan|nın)?\b", "son dört hafta"),
        (r"\bson (?:otuz|30) gün(?:ü|e|de|den)?\b", "son 30 gün"),
        (r"\b(?:geçen|son) hafta(?:yı|ya|daki|da|dan|nın)?\b", "geçen hafta"),
        (r"\bson (?:iki|2) hafta(?:yı|ya|daki|da|dan|nın)?\b", "son iki hafta"),
        (r"\bbu ay\b", "bu ay"),
        (r"\bbu hafta\b", "bu hafta"),
        (r"\bdün\b", "dün"),
        (r"\bbugün\b", "bugün"),
        (r"\b(?:şu anda|şimdi|en güncel)\b", "en güncel"),
    )
)


def extract_period_phrase(utterance: str) -> str:
    """Return a parser-supported period without using semantic inference."""
    text = normalize_phrase(utterance)
    named_range = _NAMED_MONTH_RANGE.search(text)
    if named_range:
        return named_range.group(0)
    named_month = _NAMED_MONTH.search(text)
    if named_month:
        return named_month.group(0)
    for pattern, canonical in _PERIOD_PATTERNS:
        if pattern.search(text):
            return canonical
    return ""
