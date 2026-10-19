"""Bounded EN/TR corrections; unresolved exclusions must not execute."""

from __future__ import annotations

import re

from skill.services.language import normalize_phrase


def affirmative_request(utterance: str) -> str | None:
    """Keep an explicit replacement clause, or abstain on a bare negation.

    Retain source punctuation for clause boundaries. This deliberately handles
    command corrections, not arbitrary linguistic negation or multi-intent NLP.
    """
    patterns = (
        r"^\s*(?:do not|don't|don’t|not)\b.+?[,;]\s*(?:instead\s*[,;]?\s*)?(.+)$",
        r"^\s*no\s*[,;]\s*(.+)$",
        r"^\s*not\b.+?\s+but\s+(.+)$",
        r"^.*?\b(?:değil|degil)\b\s*[,;]?\s*(.+)$",
        r"^.*?\b(?:gösterme|gosterme|listeleme|karşılaştırma|karsilastirma)\b"
        r"\s*[,;]?\s*(?:onun yerine|bunun yerine|yerine)\s+(.+)$",
    )
    trailing_exclusion = re.match(
        r"^(.+?)[,;]\s*(?:not\s+.+|.+\s+(?:değil|degil))\s*[.!?]?$",
        utterance, re.IGNORECASE,
    )
    if trailing_exclusion and not _is_exclusion(trailing_exclusion.group(1)):
        # Keep the established conservative asset-exclusion boundary. Removing
        # a negated participant is not the same as replacing an operation.
        if re.search(r"\b(?:compare|versus|vs|karşılaştır|karsilastir)\b",
                     normalize_phrase(trailing_exclusion.group(1))):
            return None
        return trailing_exclusion.group(1).strip()
    for pattern in patterns:
        match = re.match(pattern, utterance, re.IGNORECASE)
        if match:
            replacement = re.sub(
                r"\b(?:instead|onun yerine|bunun yerine)\b", "", match.group(1),
                flags=re.IGNORECASE,
            ).strip(" ,;.")
            if not replacement or _is_exclusion(replacement):
                return None
            # Subject corrections must not discard an explicit enclosing period.
            from skill.services.period_resolution import extract_period_phrase

            period = extract_period_phrase(utterance[:match.start(1)])
            if period and not extract_period_phrase(replacement):
                replacement = f"{replacement} {period}"
            return replacement
    # "Show metrics instead of findings" also excludes the trailing subject.
    match = re.match(r"^(.+?)\s+instead of\s+.+$", utterance, re.IGNORECASE)
    if match and not _is_exclusion(match.group(1)):
        return match.group(1).strip()
    match = re.match(r"^.+?\s+yerine\s+(.+)$", utterance, re.IGNORECASE)
    if match and not _is_exclusion(match.group(1)):
        return match.group(1).strip()
    return None if _is_exclusion(utterance) else utterance


def _is_exclusion(utterance: str) -> bool:
    text = normalize_phrase(utterance)
    return bool(re.search(
        r"^(?:do not|don t|not|no)\b|"
        r"\b(?:değil|degil|gösterme|gosterme|listeleme|karşılaştırma|karsilastirma)\b",
        text,
    ))
