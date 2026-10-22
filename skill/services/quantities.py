"""Bounded EN/TR number words, used only inside explicit quantity expressions.

The original utterance and source-owned names are never rewritten for routing.
Unsupported number grammar remains unchanged so callers can clarify.
"""

from __future__ import annotations

import re
from decimal import Decimal

from skill.services.language import fold_case

_EN = dict(
    zip(
        [
            "zero",
            "one",
            "two",
            "three",
            "four",
            "five",
            "six",
            "seven",
            "eight",
            "nine",
            "ten",
            "eleven",
            "twelve",
            "thirteen",
            "fourteen",
            "fifteen",
            "sixteen",
            "seventeen",
            "eighteen",
            "nineteen",
        ],
        range(20),
    )
)
_EN.update(
    dict(
        zip(
            [
                "twenty",
                "thirty",
                "forty",
                "fifty",
                "sixty",
                "seventy",
                "eighty",
                "ninety",
            ],
            range(20, 100, 10),
        )
    )
)
_TR = dict(
    zip(
        ["sıfır", "bir", "iki", "üç", "dört", "beş", "altı", "yedi", "sekiz", "dokuz"],
        range(10),
    )
)
_TR.update(
    dict(
        zip(
            [
                "on",
                "yirmi",
                "otuz",
                "kırk",
                "elli",
                "altmış",
                "yetmiş",
                "seksen",
                "doksan",
            ],
            range(10, 100, 10),
        )
    )
)
_TR.update(
    {
        "sifir": 0,
        "uc": 3,
        "dort": 4,
        "bes": 5,
        "alti": 6,
        "kirk": 40,
        "altmis": 60,
        "yetmis": 70,
    }
)


def parse_number_words(text: str) -> str | None:
    """Parse nonnegative cardinal words with optional decimal digits and sign."""
    text = fold_case(text).strip()
    if re.fullmatch(r"[-+]?\d+(?:[.,]\d+)?", text):
        return text.replace(",", ".")
    words = text.replace("-", " ").split()
    sign = ""
    if words and words[0] in {"minus", "negative", "eksi"}:
        sign, words = "-", words[1:]
    for vocabulary, hundred, thousand, decimal in (
        (_EN, "hundred", "thousand", "point"),
        (_TR, "yüz", "bin", "virgül"),
    ):
        tokens = (
            [w.replace("yuz", "yüz").replace("virgul", "virgül") for w in words]
            if vocabulary is _TR
            else words[:]
        )
        fraction = ""
        if decimal in tokens:
            if tokens.count(decimal) != 1:
                continue
            index = tokens.index(decimal)
            digits = tokens[index + 1 :]
            if not digits or any(
                w not in vocabulary or vocabulary[w] > 9 for w in digits
            ):
                continue
            fraction = "." + "".join(str(vocabulary[w]) for w in digits)
            tokens = tokens[:index]

        def under_hundred(parts, vocabulary=vocabulary):
            if len(parts) == 1 and parts[0] in vocabulary:
                return vocabulary[parts[0]]
            if (
                len(parts) == 2
                and parts[0] in vocabulary
                and parts[1] in vocabulary
                and vocabulary[parts[0]] >= (20 if vocabulary is _EN else 10)
                and vocabulary[parts[0]] % 10 == 0
                and 1 <= vocabulary[parts[1]] <= 9
            ):
                return vocabulary[parts[0]] + vocabulary[parts[1]]
            return None

        def triplet(parts, vocabulary=vocabulary, hundred=hundred, under_hundred=under_hundred):
            if hundred not in parts:
                return under_hundred(parts)
            if parts.count(hundred) != 1:
                return None
            index = parts.index(hundred)
            prefix = parts[:index]
            multiple = 1 if not prefix and vocabulary is _TR else under_hundred(prefix)
            if multiple is None or not 1 <= multiple <= 9:
                return None
            tail = parts[index + 1 :]
            if tail[:1] == ["and"] and vocabulary is _EN:
                tail = tail[1:]
                if not tail:
                    return None
            remainder = under_hundred(tail) if tail else 0
            return multiple * 100 + remainder if remainder is not None else None

        if thousand in tokens:
            if tokens.count(thousand) != 1:
                continue
            index = tokens.index(thousand)
            prefix = tokens[:index]
            multiple = 1 if not prefix and vocabulary is _TR else triplet(prefix)
            remainder = triplet(tokens[index + 1 :]) if tokens[index + 1 :] else 0
            value = (
                multiple * 1000 + remainder
                if multiple and remainder is not None
                else None
            )
        else:
            value = triplet(tokens)
        if value is not None:
            return sign + str(value) + fraction
    return None


def normalize_quantity_expressions(text: str) -> str:
    """Normalize durations and scenario amounts, never standalone name tokens."""
    text = fold_case(text)
    # Greedy quantity capture intentionally rejects partially understood phrases.
    quantity = r"([\w.,+\-]+(?:[ -]+[\w.,+\-]+){0,8}?)"

    def replace(match):
        number = parse_number_words(match.group("number"))
        attached_suffix = ""
        if number is None and re.search(
            r"yüzde|yuzde|percent|%", match.group("prefix")
        ):
            raw = match.group("number")
            if raw[-1:] in {"a", "e"}:
                number = parse_number_words(raw[:-1])
                attached_suffix = " " + raw[-1:]
        if number is None:
            return match.group(0)
        return match.group("prefix") + number + attached_suffix + match.group("suffix")

    patterns = (
        rf"(?P<prefix>\b(?:last|past|son)\s+)(?P<number>{quantity})(?P<suffix>\s+(?:days?|weeks?|gün\w*|gun\w*|hafta\w*)\b)",
        rf"(?P<prefix>\b(?:yüzde|yuzde|percent)\s+|%\s*)(?P<number>{quantity})(?P<suffix>(?:['’][ae])?(?=\s+(?:ol\w*|art\w*|azal\w*|düş\w*|dus\w*|çık\w*|cik\w*|yüksel\w*|yuksel\w*|iner\w*|ulaş\w*|ulas\w*)\b|[?!.]*$))",
        rf"(?P<prefix>\b(?:by|to|reach|reaches|becomes?)\s+)(?P<number>{quantity})(?P<suffix>\s*(?:percent\b|%))",
    )
    for pattern in patterns:
        text = re.sub(pattern, replace, text)
    words = "|".join(
        sorted(
            set(_EN)
            | set(_TR)
            | {
                "hundred",
                "thousand",
                "and",
                "point",
                "yüz",
                "yuz",
                "bin",
                "virgül",
                "virgul",
                "minus",
                "eksi",
            },
            key=len,
            reverse=True,
        )
    )
    text = re.sub(
        rf"(?P<prefix>(?<![\w-]))(?P<number>(?:{words})(?:[ -]+(?:{words}))*)(?P<suffix>\s+percent\b)",
        replace,
        text,
    )
    return text


def quantity_number(
    value: float, language: str = "en-US", *, grouped: bool = True
) -> str:
    """Shared two-decimal precision, preserving small nonzero values without exponents."""
    number = Decimal(str(value))
    places = max(2, 2 - number.copy_abs().adjusted()) if number else 2
    result = (
        format(number, f"{',' if grouped else ''}.{places}f").rstrip("0").rstrip(".")
    )
    return (
        result.translate(str.maketrans({",": ".", ".": ","}))
        if language.startswith("tr")
        else result
    )
