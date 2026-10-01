"""Speech rendering must preserve canonical text and unmatched names."""

import pytest
from services.piper_pronunciation import render_piper_text


@pytest.mark.parametrize("language", ["tr", "tr-TR", " TR-tr "])
def test_longest_name_is_rendered_as_one_phoneme_block(language):
    text = "İlgili metrik Temperature - Open Weather; Temperature için gözlem var."
    assert render_piper_text(text, language) == (
        "İlgili metrik [[tˈɛmpɹɪtʃɚ ˈoʊpən wˈɛðɚ]]; "
        "[[tˈɛmpɹɪtʃɚ]] için gözlem var."
    )


@pytest.mark.parametrize("language", ["en-US", "en-GB", "de-DE", ""])
def test_other_languages_are_unchanged(language):
    text = "Temperature - Open Weather"
    assert render_piper_text(text, language) == text


def test_unknown_names_substrings_and_metadata_are_unchanged():
    text = "Humidity, Rain, MyTemperature, TemperatureSensor, TEMPERATURE, temperature."
    assert render_piper_text(text, "tr-TR") == text


def test_punctuation_and_turkish_suffix_are_preserved():
    assert render_piper_text("(Temperature), Temperature'ın eğilimi.", "tr-TR") == (
        "([[tˈɛmpɹɪtʃɚ]]), [[tˈɛmpɹɪtʃɚ]]'ın eğilimi."
    )


def test_existing_phoneme_blocks_are_preserved_and_rendering_is_idempotent():
    text = "[[Temperature]] Temperature - Open Weather."
    rendered = render_piper_text(text, "tr-TR")
    assert rendered == "[[Temperature]] [[tˈɛmpɹɪtʃɚ ˈoʊpən wˈɛðɚ]]."
    assert render_piper_text(rendered, "tr-TR") == rendered
