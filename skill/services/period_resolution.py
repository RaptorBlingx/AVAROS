"""Deterministic bilingual period extraction for conversational queries."""

from __future__ import annotations

import calendar
import re

from skill.services.language import normalize_phrase
from skill.services.quantities import normalize_quantity_expressions

_MONTH_NAMES = (
    "|".join(month.lower() for month in calendar.month_name[1:])
    + r"|ocak|şubat|subat|mart|nisan|mayıs|mayis|haziran|temmuz|ağustos|agustos|eylül|eylul|ekim|kasım|kasim|aralık|aralik"
)
_NAMED_MONTH_RANGE = re.compile(
    rf"\b({_MONTH_NAMES})(?:\s+(\d{{4}}))?\s*(?:to|through|and|ile|-|dan|den)\s*"
    rf"({_MONTH_NAMES})\s+(\d{{4}})(?:\s+(?:ya|ye|a|e))?\b"
)
_NAMED_MONTH = re.compile(rf"\b(?:{_MONTH_NAMES})\s+\d{{4}}\b")

# Case and possessive endings belong to the shared calendar expression,
# including forms such as ayının / haftasının, rather than subject text.
_TR_CALENDAR_SUFFIX = r"(?:ı|i|ın|in|ının|inin|nın|nin|sının|sinin|a|e|yı|yi|ya|ye|da|de|dan|den|daki|deki|ında|inde|ındaki|indeki)?"

_PERIOD_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = tuple(
    (re.compile(pattern), canonical)
    for pattern, canonical in (
        (r"\b(?:previous|prior|last) calendar month\b", "last month"),
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
            rf"\b(?:geçen|gecen|önceki|onceki) (?:takvim )?ay{_TR_CALENDAR_SUFFIX}\b",
            "geçen ay",
        ),
        (rf"\bson ay{_TR_CALENDAR_SUFFIX}\b", "son ay"),
        (rf"\bson (?:dört|4) hafta{_TR_CALENDAR_SUFFIX}\b", "son dört hafta"),
        (r"\bson (?:otuz|30) gün(?:ü|e|de|den)?\b", "son 30 gün"),
        (rf"\b(?:geçen|son) hafta{_TR_CALENDAR_SUFFIX}\b", "geçen hafta"),
        (rf"\bson (?:iki|2) hafta{_TR_CALENDAR_SUFFIX}\b", "son iki hafta"),
        (rf"\bbu ay{_TR_CALENDAR_SUFFIX}\b", "bu ay"),
        (rf"\bbu hafta{_TR_CALENDAR_SUFFIX}\b", "bu hafta"),
        (r"\b(?:dün|dun)(?:kü|ku)?\b", "dün"),
        (r"\b(?:bugün|bugun)(?:kü|ku)?\b", "bugün"),
        (r"\b(?:şu anda|şimdi|en güncel)\b", "en güncel"),
    )
)


def extract_period_phrase(utterance: str) -> str:
    """Return a parser-supported period without using semantic inference."""
    text = normalize_phrase(normalize_quantity_expressions(utterance))
    iso_range = re.search(
        r"\b\d{4}-\d{2}-\d{2}\s+(?:to|through|until|ile|ila)\s+\d{4}-\d{2}-\d{2}\b",
        text,
    )
    if iso_range:
        return iso_range.group(0)
    iso_day = re.search(r"\b\d{4}-\d{2}-\d{2}\b", text)
    if iso_day:
        return iso_day.group(0)
    # Canonicalize a named day into the existing explicit-date parser.
    months = {name.lower(): i for i, name in enumerate(calendar.month_name) if name}
    months.update(
        dict(
            zip(
                [
                    "ocak",
                    "şubat",
                    "mart",
                    "nisan",
                    "mayıs",
                    "haziran",
                    "temmuz",
                    "ağustos",
                    "eylül",
                    "ekim",
                    "kasım",
                    "aralık",
                ],
                range(1, 13),
            )
        )
    )
    months.update({"mayis": 5, "subat": 2, "agustos": 8,
                   "eylul": 9, "kasim": 11, "aralik": 12})
    named_day = re.search(
        rf"\b({_MONTH_NAMES})\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,)?\s+(\d{{4}})\b", text
    )
    day_first = re.search(
        rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+({_MONTH_NAMES})(?:,)?\s+(\d{{4}})\b", text
    )
    if named_day or day_first:
        if named_day:
            month, day, year = named_day.groups()
        else:
            day, month, year = day_first.groups()
        return f"{int(year):04d}-{months[month]:02d}-{int(day):02d}"
    named_range = _NAMED_MONTH_RANGE.search(text)
    if named_range:
        if not re.search(r"\b(?:dan|den)\b", named_range.group(0)):
            return named_range.group(0)
        first, first_year, last, last_year = named_range.groups()
        return f"{first} {first_year or last_year} to {last} {last_year}"
    named_month = _NAMED_MONTH.search(text)
    if named_month:
        return named_month.group(0)
    days = re.search(r"\b(?:last|past|son) (\d+) (days|weeks|gün(?:ün|ü|e|de|den|deki|lük|ler)?|gun(?:un|u|e|de|den|deki|luk|ler)?|hafta\w*)\b", text)
    if days and not (int(days.group(1)) in {2, 4} and days.group(2).startswith(("week", "hafta"))):
        return (
            f"last {days.group(1)} {'weeks' if days.group(2) == 'weeks' else 'days'}"
            if not text[days.start() :].startswith("son")
            else f"son {days.group(1)} {'hafta' if days.group(2).startswith('hafta') else 'gün'}"
        )
    for pattern, canonical in _PERIOD_PATTERNS:
        if pattern.search(text):
            return canonical
    if re.search(r"\b(?:this year|bu yıl|bu yil)\b", text):
        return "bu yıl" if "bu yıl" in text or "bu yil" in text else "this year"
    years = re.findall(r"\b(?:19|20)\d{2}\b", text)
    return years[0] if len(years) == 1 else ""


def named_month_reference(utterance: str) -> bool:
    return bool(
        re.search(
            rf"\b(?:{_MONTH_NAMES})(?:\b|(?:ın|ında| ayında)\b)",
            normalize_phrase(utterance),
        )
    )


def remove_period_reference(utterance: str) -> str:
    """Remove the matched source wording, even when its parser phrase differs."""
    text = normalize_phrase(normalize_quantity_expressions(utterance))
    phrase = extract_period_phrase(utterance)
    if phrase:
        for pattern, canonical in _PERIOD_PATTERNS:
            if canonical == phrase:
                text = pattern.sub("", text)
        text = text.replace(phrase, "")
        text = re.sub(r"\b(?:last|past|son) \d+ (?:days|weeks|gün(?:ün|ü|e|de|den|deki|lük|ler)?|gun(?:un|u|e|de|den|deki|luk|ler)?|hafta\w*)\b", "", text)
    return text


def unsupported_period_reference(utterance: str) -> bool:
    """An unrecognized explicit time reference must not become a default window."""
    if unsupported_time_precision(utterance):
        return True
    text = normalize_phrase(normalize_quantity_expressions(utterance))
    phrase = extract_period_phrase(utterance)
    relative_spans = sorted({m.span() for pattern, _ in _PERIOD_PATTERNS
                             for m in pattern.finditer(text)})
    disjoint = []
    for start, end in relative_spans:
        if not disjoint or start >= disjoint[-1][1]:
            disjoint.append((start, end))
    if len(disjoint) > 1:
        return True
    # These windows are outside the current parser contract. Reject them even
    # alongside a recognized date rather than retaining/defaulting a window.
    if re.search(
        r"\b(?:next|coming|following) (?:calendar )?(?:day|week|month|year)s?\b|"
        r"\b(?:tomorrow|yarın|yarin)\b|"
        r"\b(?:gelecek|önümüzdeki|onumuzdeki|sonraki) (?:gün|gun|hafta|ay|yıl|yil)\w*\b|"
        r"\b(?:last|previous|prior|past) (?:calendar )?year\b|"
        r"\b(?:geçen|gecen|önceki|onceki|son) (?:yıl|yil|sene)\w*\b",
        text,
    ):
        return True
    if re.search(r"\b(?:q[1-4]|quarter|çeyrek|ceyrek)\b|\d{1,2}/\d{1,2}/\d{2,4}", text):
        return True
    if named_month_reference(text) and re.fullmatch(r"(?:19|20)\d{2}", phrase):
        return True
    if len(
        re.findall(rf"\b(?:{_MONTH_NAMES})\b", text)
    ) > 1 and not _NAMED_MONTH_RANGE.search(text):
        return True
    # Multiple dates are supported only by a recognized range, never by its first date.
    if len(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text)) > 1:
        return not bool(re.search(r"(?:to|through|until|ile|ila)", phrase))
    if len(re.findall(r"\b(?:19|20)\d{2}\b", text)) > 1:
        return not bool(
            _NAMED_MONTH_RANGE.search(text)
            or re.search(r"\d{4}-\d{2}-\d{2}\s+(?:to|through|until|ile|ila)", text)
        )
    return not phrase and (
        named_month_reference(text)
        or bool(
            re.search(
                r"\b(?:last|past|previous|prior|son|geçen|gecen|önceki|onceki) "
                r"[^.!?]*\b(?:days?|weeks?|months?|years?|gün(?:ün|ü|e|de|den|deki|lük|ler)?|gun(?:un|u|e|de|den|deki|luk|ler)?|hafta\w*|ay(?:ın|in|da|dan|ı|i)?|yıl\w*|yil\w*)\b|"
                r"\b(?:this year|bu yıl|bu yil)\b", text
            )
        )
    )


def unsupported_time_precision(utterance: str) -> bool:
    """Detect clock-time qualifiers the MVP's day-or-coarser queries cannot honor.

    Inspect the source text before phrase normalization removes clock separators.
    A supported date alongside a clock time does not make that precision supported.
    """
    return bool(re.search(
        r"(?<!\w)\d{1,2}\s*:\s*\d{2}(?:\s*:\s*\d{2})?(?!\d)|"
        r"\b\d{4}-\d{2}-\d{2}t\d{2}\s*:\s*\d{2}|"
        r"\b(?:at|saat)\s+\d{1,2}(?:\s*[.:]\s*\d{2})?(?![\w-])|"
        r"\b\d{1,2}(?:[.:]\d{2})?\s*[ap]\.?m\.?(?!\w)|"
        r"(?<!\w)\d{1,2}\.\d{2}\s*['’]?(?:de|da|te|ta|den|dan|ten|tan)\b|"
        r"\bat\s+(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty)\b|"
        r"\bsaat\s+(?:bir|iki|üç|uc|dört|dort|beş|bes|altı|alti|yedi|sekiz|dokuz|on)\b|"
        r"\b(?:noon|midnight|öğlen|gece yarısı)\b",
        utterance, re.IGNORECASE,
    ))
