"""Speech rendering must preserve canonical text and unmatched names."""

import pytest
from services.piper_pronunciation import render_piper_text


@pytest.mark.parametrize("language", ["tr", "tr-TR", " TR-tr "])
def test_full_metric_uses_turkish_term_and_retains_english_source(language):
    text = "İlgili metrik Temperature - Open Weather; Temperature için gözlem var."
    assert render_piper_text(text, language) == (
        "İlgili metrik hava sıcaklığı, [[ˈoʊpən wˈɛðɚ]]; "
        "[[tˈɛmpɹɪtʃɚ]] için gözlem var."
    )


@pytest.mark.parametrize("language", ["en-US", "en-GB", "de-DE", ""])
def test_other_languages_are_unchanged(language):
    text = (
        "Temperature - Open Weather, Cooling degree days - Open Weather, "
        "Heating degree days - Open Weather, Humidity, Rain, OpenWeather."
    )
    assert render_piper_text(text, language) == text


def test_unknown_names_substrings_and_metadata_are_unchanged():
    text = (
        "Unknown English Metric, MyTemperature, TemperatureSensor, "
        "HumiditySensor, Rainfall, OpenWeatherStation, TEMPERATURE, GAUGE, "
        "OPEN_WEATHER, temperature, humidity, rain."
    )
    assert render_piper_text(text, "tr-TR") == text


def test_punctuation_and_turkish_suffix_are_preserved():
    assert render_piper_text("(Temperature), Temperature'ın eğilimi.", "tr-TR") == (
        "([[tˈɛmpɹɪtʃɚ]]), [[tˈɛmpɹɪtʃɚ]]'ın eğilimi."
    )


def test_existing_phoneme_blocks_are_preserved_and_rendering_is_idempotent():
    text = "[[Temperature]] Temperature - Open Weather."
    rendered = render_piper_text(text, "tr-TR")
    assert rendered == "[[Temperature]] hava sıcaklığı, [[ˈoʊpən wˈɛðɚ]]."
    assert render_piper_text(rendered, "tr-TR") == rendered


@pytest.mark.parametrize(
    ("name", "spoken", "phonemes"),
    [
        ("Cooling degree days", "soğutma derece gün değeri", "kˈuːlɪŋ dᵻɡɹˈiː dˈeɪz"),
        ("Heating degree days", "ısıtma derece gün değeri", "hˈiːɾɪŋ dᵻɡɹˈiː dˈeɪz"),
        ("Humidity", "hava nemi", "hjuːmˈɪdᵻɾi"),
        ("Rain", "yağış miktarı", "ɹˈeɪn"),
    ],
)
def test_full_names_use_turkish_terms_and_short_names_keep_english(name, spoken, phonemes):
    original = f"İlgili metrik {name} - Open Weather; {name} için dönem seçebilirsiniz."
    rendered = render_piper_text(original, "tr-TR")
    assert rendered == (
        f"İlgili metrik {spoken}, [[ˈoʊpən wˈɛðɚ]]; "
        f"[[{phonemes}]] için dönem seçebilirsiniz."
    )
    assert render_piper_text(rendered, "tr-TR") == rendered


@pytest.mark.parametrize("name", ["OpenWeather", "Open Weather"])
def test_reviewed_source_name_spellings_share_pronunciation(name):
    assert render_piper_text(f"İlgili kaynak {name}.", "tr-TR") == (
        "İlgili kaynak [[ˈoʊpən wˈɛðɚ]]."
    )


@pytest.mark.parametrize(
    ("name", "phonemes"),
    [("Humidity", "hjuːmˈɪdᵻɾi"), ("Rain", "ɹˈeɪn")],
)
def test_reviewed_names_keep_turkish_suffixes(name, phonemes):
    assert render_piper_text(f"{name}'in eğilimini sorabilirsiniz.", "tr-TR") == (
        f"[[{phonemes}]]'in eğilimini sorabilirsiniz."
    )


def test_future_gen_suffixes_urls_and_idempotence():
    text = "Future Gen'in verileri: https://example.test/OpenWeather/Temperature"
    rendered = render_piper_text(text, "tr-TR")
    assert rendered == "[[fjˈuːtʃɚ dʒˈɛn]]'in verileri: https://example.test/OpenWeather/Temperature"
    assert render_piper_text(rendered, "tr-TR") == rendered
    assert render_piper_text(text, "en-US") == text
