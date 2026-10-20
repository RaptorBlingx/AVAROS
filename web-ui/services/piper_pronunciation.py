"""Curated speech-only names and terminology for Turkish Piper."""

from __future__ import annotations

import re

# Piper 1.4.2 raw phonemes supported by tr_TR-dfki-medium. Future Gen's
# pronunciation was accepted in listening review; Open Weather is retained.
# Keep exact, case-sensitive spellings to avoid rewriting metadata enums.
_PRONUNCIATIONS = {
    # Keep short source-name forms in English, including attached Turkish suffixes.
    "Temperature": "tˈɛmpɹɪtʃɚ",
    "Humidity": "hjuːmˈɪdᵻɾi",
    "Rain": "ɹˈeɪn",
    "Heating degree days": "hˈiːɾɪŋ dᵻɡɹˈiː dˈeɪz",
    "Cooling degree days": "kˈuːlɪŋ dᵻɡɹˈiː dˈeɪz",
    "Future Gen": "fjˈuːtʃɚ dʒˈɛn",
    "Open Weather": "ˈoʊpən wˈɛðɚ",
    "OpenWeather": "ˈoʊpən wˈɛðɚ",
}
# Match the established Turkish narration vocabulary, including when dynamic
# finding/source labels reach Piper without response-level localization.
# Retain source attribution in full labels; displayed names stay canonical.
_TURKISH_METRIC_TERMS = {
    "Temperature": "hava sıcaklığı",
    "Humidity": "hava nemi",
    "Rain": "yağış miktarı",
    "Heating degree days": "ısıtma derece gün değeri",
    "Cooling degree days": "soğutma derece gün değeri",
}
_SPEECH_REPLACEMENTS = {
    **{name: f"[[{phonemes}]]" for name, phonemes in _PRONUNCIATIONS.items()},
    **{
        f"{name} - Open Weather": f"{spoken}, [[{_PRONUNCIATIONS['Open Weather']}]]"
        for name, spoken in _TURKISH_METRIC_TERMS.items()
    },
}
_NAME_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(name) for name in sorted(_SPEECH_REPLACEMENTS, key=len, reverse=True))
    + r")(?!\w)"
)
_RAW_PHONEME_PATTERN = re.compile(r"(\[\[.*?\]\]|https?://\S+)", re.DOTALL)


def render_piper_text(text: str, language: str) -> str:
    """Render curated names/terms only in transient Turkish Piper input."""
    if not language.strip().lower().startswith("tr"):
        return text

    # Preserve raw phonemes and URLs, and make rendering idempotent.
    parts = _RAW_PHONEME_PATTERN.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = _NAME_PATTERN.sub(
            lambda match: _SPEECH_REPLACEMENTS[match.group(0)], parts[index]
        )
    return "".join(parts)
