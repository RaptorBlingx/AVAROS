"""D06: presentation changes preserve trusted context and canonical result data."""

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skill import AVAROSSkill
from skill._reneryo_handlers import _conversation_language, handle_reneryo_query
from skill.domain.exceptions import AdapterError, AssetNotFoundError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoMeter
from skill.domain.results import KPIResult
from skill.services.conversation_state import DialogueState
from skill.services.dia_dialogue import _speak_result_collection
from skill.services.dia_response import speak_with_evidence
from skill.services.futuregen_responses import metric_detail_headline, meter_inventory_headline
from skill.services.language import period_display_name, source_enum_label
from skill.services.response_builder import create_response_builder
from skill.services.response_localization import localized_error_message
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_finding_collection_dialogue import _message


@pytest.mark.parametrize("text,locale", [
    ("Show Tesis Toplam Üretim Miktarı", "en-US"),
    ("Peki Haziran?", "tr-TR"),
    ("And production for the same period?", "en-US"),
])
def test_validated_current_turn_locale_outweighs_source_name_and_prior(text, locale):
    message = _message(text, locale)
    message.context["reneryo_widget_session_validated"] = True
    before = deepcopy((message.data, message.context))
    assert _conversation_language(text, DialogueState(language="tr-TR"), message, "tr-TR") == locale
    assert (message.data, message.context) == before


def test_language_switch_preserves_period_topic_and_original_input():
    skill = harness()
    turns = [
        ("Show electricity consumption in June 2020", "en-US", "Reneryo period consumption"),
        ("Peki Haziran?", "tr-TR", "Reneryo dönem tüketimi"),
        ("And production for the same period?", "en-US", "Reneryo monthly period values"),
    ]
    for text, locale, expected in turns:
        message = _message(text, locale)
        message.context["reneryo_widget_session_validated"] = True
        before = deepcopy((message.data, message.context))
        assert handle_reneryo_query(skill, message)
        answer = response(skill)
        assert answer["language"] == locale
        assert expected in answer["headline"]
        assert answer["evidence_rows"]
        assert (message.data, message.context) == before
    state = skill._dialogue_state_store.get("collection-session")
    assert state.period.start == datetime(2020, 6, 1, tzinfo=timezone.utc)
    assert state.period.end == datetime(2020, 7, 1, tzinfo=timezone.utc)
    assert "haziran" not in response(skill)["headline"]
    assert "june 2020" in response(skill)["headline"].lower()


@pytest.mark.parametrize("label,locale,expected", [
    ("latest available", "tr-TR", "mevcut en güncel"),
    ("yesterday", "tr-TR", "dün"),
    ("June 2020", "tr-TR", "Haziran 2020"),
    ("haziran 2020", "en-US", "June 2020"),
    ("2020-06-01 – 2020-06-30", "tr-TR", "2020-06-01 – 2020-06-30"),
])
def test_period_labels_are_presentation_only(label, locale, expected):
    assert period_display_name(label, locale) == expected


def result(value=82.5):
    return KPIResult(
        metric=CanonicalMetric.OEE, value=value, unit="%", asset_id="Line-10",
        period=TimePeriod.latest(), timestamp=datetime(2020, 7, 1, tzinfo=timezone.utc),
    )


def presenter(language):
    skill = SimpleNamespace(_response_language=language, speak=Mock())
    skill.response_builder = create_response_builder(language, asset_name_resolver=lambda _: "Cooling degree days - Open Weather")
    return skill


def test_turkish_collection_localizes_owned_words_and_preserves_source_name_and_values():
    skill = presenter("tr-TR")
    rows = [result(), result(75)]
    before = deepcopy(rows)
    _speak_result_collection(skill, "KPI results", rows)
    text = skill.speak.call_args.args[0]
    metadata = skill.speak.call_args.kwargs["meta"]["avaros_response"]
    assert metadata["headline"] == "KPI sonuçları: Cooling degree days - Open Weather toplam ekipman etkinliği yüzde 82,5; Cooling degree days - Open Weather toplam ekipman etkinliği yüzde 75."
    assert "ka pe i sonuçları" in text and "yüzde seksen iki virgül beş" in text
    assert text == metadata["speech_text"]
    assert metadata["language"] == "tr-TR"
    assert [r["value"] for r in metadata["evidence_rows"]] == [82.5, 75]
    assert all(r["asset_id"] == "Line-10" and r["unit"] == "%" and r["metric"] == "oee" for r in metadata["evidence_rows"])
    assert rows == before


def test_evidence_and_suggestions_have_current_locale_without_changing_contract_data():
    skill = presenter("tr-TR")
    row = result()
    speak_with_evidence(skill, skill.response_builder.format_kpi_result(row), row)
    metadata = skill.speak.call_args.kwargs["meta"]["avaros_response"]
    assert metadata["language"] == "tr-TR"
    assert metadata["evidence_rows"][0]["metric_label"] == "toplam ekipman etkinliği"
    assert metadata["evidence_rows"][0]["value"] == 82.5
    assert metadata["period"]["start"] == row.period.start.isoformat()
    assert metadata["period"]["end"] == row.period.end.isoformat()
    assert all("Line-10" in text or "Tüm hatlar" in text for text in metadata["suggested_follow_ups"])
    assert "latest available" not in skill.speak.call_args.args[0]


def test_known_metadata_enums_are_not_record_names_or_unit_conversions():
    metric = ReneryoMetric("source-id", "PIECE - Open Weather", "COUNTER", "PIECE", 5000.25)
    text = metric_detail_headline(metric, "tr-TR")
    assert "PIECE - Open Weather" in text
    assert "birikimli sayaç" in text and "5.000,25 adet" in text
    assert source_enum_label("UNKNOWN_SOURCE_CATEGORY", "tr-TR") == "UNKNOWN_SOURCE_CATEGORY"
    assert source_enum_label("ENERGY", "tr-TR") == "enerji"
    assert "kWh" not in text
    meter = ReneryoMeter("m", "ELECTRIC", "ELECTRIC", 12.5, "source-id", metric.name)
    text = meter_inventory_headline([meter], TimePeriod.latest(), "tr-TR")
    assert "sayaç var: ELECTRIC" in text and "Enerji kaynağı elektrik" in text
    assert "12,5" in text and "PIECE - Open Weather" in text


@pytest.mark.parametrize("language,expected", [("en-US", "Reneryo data is temporarily unavailable."), ("tr-TR", "Reneryo verilerine şu anda erişilemiyor.")])
def test_safe_dispatch_localizes_failure_and_warning(language, expected):
    skill = presenter(language)
    skill._ensure_runtime_services = lambda: None
    skill._check_profile_mismatch = lambda: None
    skill.dispatcher = object()
    skill.log = Mock()
    error = AdapterError("synthetic HTTP 503", code="RENERYO_REQUEST_FAILED", user_message="Reneryo data is temporarily unavailable.")
    assert AVAROSSkill._safe_dispatch(skill, "synthetic", lambda: (_ for _ in ()).throw(error)) is None
    assert skill.speak.call_args.args[0] == expected
    metadata = skill.speak.call_args.kwargs["meta"]["avaros_response"]
    assert metadata["language"] == language and metadata["warnings"] == [expected]
    assert error.user_message == "Reneryo data is temporarily unavailable."


def test_asset_identifier_is_preserved_in_localized_error():
    error = AssetNotFoundError("missing", asset_id="Cooling degree days - Open Weather")
    assert localized_error_message(error, "tr-TR") == "Cooling degree days - Open Weather adlı ekipman bulunamadı."


@pytest.mark.parametrize("locale,expected", [
    ("tr-TR", "Bu isteği yapılandırılmış bir üretim sorusuyla eşleştiremedim."),
    ("en-US", "I couldn't map that to a configured manufacturing question."),
])
def test_final_browser_clarification_uses_current_locale_after_exhausted_recovery(monkeypatch, locale, expected):
    # Force the same terminal path reached after MDSP HTTP failure in OVOS;
    # this tests presentation without changing/repeating domain execution.
    import skill._reneryo_handlers as reneryo
    import skill._handlers as handlers
    monkeypatch.setattr(reneryo, "handle_reneryo_query", lambda *a, **k: False)
    monkeypatch.setattr(reneryo, "has_signed_widget_context", lambda _: False)
    monkeypatch.setattr(handlers, "try_handle_structured_query", lambda *a, **k: False)
    monkeypatch.setattr(handlers, "is_browser_message", lambda _: True)
    skill = presenter("en-US")
    skill._sync_response_language = lambda _: setattr(skill, "_response_language", locale)
    skill._extract_utterance_text = lambda _: "Etkin bulguları listele"
    for name in ["anomaly", "drift", "forecast", "whatif"]:
        setattr(skill, f"_is_{name}_query", lambda _: False)
    skill._resolve_metric_from_utterance = lambda _: None
    handlers.handle_intent_failure(skill, _message("Etkin bulguları listele", locale))
    assert skill.speak.call_args.args[0].startswith(expected)
    metadata = skill.speak.call_args.kwargs["meta"]["avaros_response"]
    assert metadata["language"] == locale
    assert metadata["suggested_follow_ups"][0] == ("Neler yapabilirsin?" if locale == "tr-TR" else "What can you do?")


def test_turkish_speech_preserves_quantity_meaning_and_is_idempotent():
    from skill.services.language import speech_text

    examples = {
        "15,7 °C'den 15,92 °C'ye; yaklaşık 0,22 °C artış.":
            "on beş virgül yedi dereceden on beş virgül doksan iki dereceye; yaklaşık sıfır virgül yirmi iki derecelik bir artış.",
        "25%; 100 kWh; 3,5 m³; -0,005 kg.":
            "yüzde yirmi beş; yüz kilovatsaat; üç virgül beş metreküp; eksi sıfır virgül sıfır sıfır beş kilogram.",
        "01.07.2026 00:00; saat 14:30; süre 00:00; Haziran 2026; MDSP ve OEE.":
            "bir Temmuz iki bin yirmi altı gece yarısı; saat on dört otuz; süre 00:00; Haziran iki bin yirmi altı; em de se pe ve o e e.",
    }
    examples["RMSE 10,005; R² 0,523; MDSP, OEE, KPI, UTC."] = (
        "kök ortalama kare hatası on virgül sıfır sıfır beş; er kare sıfır virgül beş yüz yirmi üç; "
        "em de se pe, o e e, ka pe i, evrensel eşgüdümlü zaman."
    )
    for written, expected in examples.items():
        assert speech_text(written, "tr-TR") == expected
        assert speech_text(expected, "tr-TR") == expected
        assert speech_text(written, "en-US") != expected
    assert speech_text("metric-123 https://example.com/123 [[raw123]]", "tr-TR") == "metric-123 https://example.com/123 [[raw123]]"


def test_known_weather_labels_are_presentation_only():
    from skill.services.response_localization import source_metric_label, localize_metric_labels

    row = ReneryoMetric("source-id", "Humidity - Open Weather", "GAUGE", "RATE", .94)
    before = deepcopy(row)
    assert "hava nemi %94" in metric_detail_headline(row, "tr-TR", value_only=True)
    assert source_metric_label(row.name, "en-US") == row.name
    assert source_metric_label("Temperature - Boiler 2", "tr-TR") == "Temperature - Boiler 2"
    assert localize_metric_labels("Temperature - Boiler 2", "tr-TR") == "Temperature - Boiler 2"
    assert row == before


@pytest.mark.parametrize('written,expected', [
    ('Temperature - Open Weather: 16,5 °C. Humidity - Open Weather: %70. Rain - Open Weather: 2,5 mm.',
     'OpenWeather verilerine göre hava sıcaklığı on altı virgül beş derece, hava nemi yüzde yetmiş ve yağış miktarı iki virgül beş milimetre.'),
    ('Bu doğrusal regresyon modeli günlük dönemlidir ve birincil değil. Eğitim dönemi 2025-01-01 – 2025-02-01; R² 0,850, RMSE 10,005.',
     'Günlük dönemli bu doğrusal regresyon modeli birincil değil. Eğitim dönemi bir Ocak iki bin yirmi beş ile bir Şubat iki bin yirmi beş. er kare sıfır virgül sekiz yüz elli, kök ortalama kare hatası on virgül sıfır sıfır beş.'),
    ('Bu birikimli sayaç değeridir; dönem tüketimi veya üretimi değildir.',
     'Bu, birikimli sayaç değeri; dönem tüketimi ya da üretimi değil.'),
])
def test_turkish_narration_preserves_facts_and_other_languages(written, expected):
    from skill.services.language import speech_text

    assert speech_text(written, 'tr-TR') == expected
    assert speech_text(expected, 'tr-TR') == expected
    for language in ('en-US', 'de-DE'):
        # Other languages retain the established quantity renderer.
        assert speech_text(written, language).startswith(written.split('. ')[0].split(':')[0])


def test_turkish_weather_does_not_merge_across_qualifiers_or_unknown_sources():
    from skill.services.language import speech_text

    written = ('Temperature - Open Weather: 16,5 °C. Veri kapsamı eksik olabilir. '
               'Humidity - Other Source: %70. https://example.com/Temperature [[raw123]]')
    spoken = speech_text(written, 'tr-TR')
    assert 'Veri kapsamı eksik olabilir.' in spoken
    assert 'Humidity - Other Source: yüzde yetmiş.' in spoken
    assert 'https://example.com/Temperature [[raw123]]' in spoken
    assert spoken.count('OpenWeather') == 1


def test_spoken_narration_leaves_written_response_and_evidence_intact():
    from skill.services.dia_response import speak_information

    skill = SimpleNamespace(speak=Mock(), _response_language='tr-TR')
    headline = 'Son ölçümde hava nemi %70. Kayıt zamanı: 01.01.2025 12:30.'
    evidence = [{'name': 'Humidity - Open Weather', 'value': .7, 'unit_group': 'RATE'}]
    original = deepcopy(evidence)
    speak_information(skill, headline, evidence_rows=evidence, warnings=['Veri kapsamı eksik olabilir.'])
    spoken = skill.speak.call_args.args[0]
    metadata = skill.speak.call_args.kwargs['meta']['avaros_response']
    assert metadata['headline'] == headline
    assert metadata['evidence_rows'] == evidence == original
    assert metadata['warnings'] == ['Veri kapsamı eksik olabilir.']
    assert 'Son kayıt bir Ocak iki bin yirmi beş saat on iki otuz.' in spoken
    assert metadata['speech_text'] == spoken
