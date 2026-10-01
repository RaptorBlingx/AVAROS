"""Explicit speech-only pronunciations for English names in Turkish Piper."""

from __future__ import annotations

import re

# Piper 1.4.2 raw phoneme syntax. These English phonemes are supported by
# tr_TR-dfki-medium. Keep canonical names and displayed responses unchanged.
# Exact, case-sensitive entries avoid treating metadata enums as names.
# Full-name and shorter-form pronunciations passed Turkish listening review.
_PRONUNCIATIONS = {
    "Cooling degree days - Open Weather": "kˈuːlɪŋ dᵻɡɹˈiː dˈeɪz ˈoʊpən wˈɛðɚ",
    "Cooling degree days": "kˈuːlɪŋ dᵻɡɹˈiː dˈeɪz",
    "Heating degree days - Open Weather": "hˈiːɾɪŋ dᵻɡɹˈiː dˈeɪz ˈoʊpən wˈɛðɚ",
    "Heating degree days": "hˈiːɾɪŋ dᵻɡɹˈiː dˈeɪz",
    "Humidity - Open Weather": "hjuːmˈɪdᵻɾi ˈoʊpən wˈɛðɚ",
    "Humidity": "hjuːmˈɪdᵻɾi",
    "Rain - Open Weather": "ɹˈeɪn ˈoʊpən wˈɛðɚ",
    "Rain": "ɹˈeɪn",
    "Open Weather": "ˈoʊpən wˈɛðɚ",
    "OpenWeather": "ˈoʊpən wˈɛðɚ",
    "Temperature - Open Weather": "tˈɛmpɹɪtʃɚ ˈoʊpən wˈɛðɚ",
    "Temperature": "tˈɛmpɹɪtʃɚ",
}
_NAME_PATTERN = re.compile(
    r"(?<!\w)(?:"
    + "|".join(re.escape(name) for name in sorted(_PRONUNCIATIONS, key=len, reverse=True))
    + r")(?!\w)"
)
_RAW_PHONEME_PATTERN = re.compile(r"(\[\[.*?\]\])", re.DOTALL)


def render_piper_text(text: str, language: str) -> str:
    """Render known names as phonemes, only for transient Turkish TTS input."""
    if not language.strip().lower().startswith("tr"):
        return text

    # Preserve existing raw phoneme blocks and make rendering idempotent.
    parts = _RAW_PHONEME_PATTERN.split(text)
    for index in range(0, len(parts), 2):
        parts[index] = _NAME_PATTERN.sub(
            lambda match: f"[[{_PRONUNCIATIONS[match.group(0)]}]]", parts[index]
        )
    return "".join(parts)
