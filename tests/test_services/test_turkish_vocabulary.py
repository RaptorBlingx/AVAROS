"""Turkish case folding and AVAROS-owned metric vocabulary contracts."""
from datetime import datetime, timezone

import pytest

from skill.domain.reneryo_models import ReneryoMetric
from skill.services.futuregen import metric_references
from skill.services.language import fold_case, normalize_phrase
from skill.services.response_localization import _TURKISH_SOURCE_METRICS

OBSERVED = datetime(2026, 10, 15, 6, tzinfo=timezone.utc)
METRICS = [
    ReneryoMetric('h', 'Humidity - Open Weather', 'GAUGE', 'RATE', .6, OBSERVED),
    ReneryoMetric('t', 'Temperature - Open Weather', 'GAUGE', 'TEMPERATURE', 17.5, OBSERVED),
    ReneryoMetric('r', 'Rain - Open Weather', 'GAUGE', 'PRECIPITATION', 1.2, OBSERVED),
    ReneryoMetric('hd', 'Heating degree days - Open Weather', 'GAUGE', 'SCALAR', 3.5, OBSERVED),
    ReneryoMetric('cd', 'Cooling degree days - Open Weather', 'GAUGE', 'SCALAR', 0.0, OBSERVED),
    ReneryoMetric('e', 'Tesis Toplam Elektrik Tüketimi', 'COUNTER', 'ENERGY', 1000.0, OBSERVED),
]


@pytest.mark.parametrize('raw,expected', [
    ('Isıtma derece gün değeri nedir?', 'ısıtma derece gün değeri nedir'),
    ('İLKİNİ AÇIKLA', 'ilkini açıkla'),
    ('HANGİ DÖNEMİ KAPSIYOR?', 'hangi dönemi kapsıyor'),
    ('Is the humidity high?', 'is the humidity high'),
    ('What is the Tesis Toplam Üretim Miktarı? Is it high', 'what is the tesis toplam üretim miktarı is it high'),
    ('IIoT sensor', 'iiot sensor'),
])
def test_case_folding_keeps_turkish_dotless_i_without_touching_english(raw, expected):
    assert normalize_phrase(raw) == expected
    assert fold_case('İkinciyi açıkla') == 'ikinciyi açıkla'


@pytest.mark.parametrize('source,label', sorted(
    (source, label) for source, label in _TURKISH_SOURCE_METRICS.items() if ' - Open Weather' in source
))
def test_every_displayed_turkish_metric_label_is_understood(source, label):
    # Users answer with the words AVAROS shows them, including inflections.
    for text in (label, label.capitalize() + ' nedir?', label + 'nin son değeri'):
        assert [m.name for m in metric_references(text, METRICS)] == [source]


@pytest.mark.parametrize('text,expected', [
    ('Son yağış miktarı nedir?', 'Rain - Open Weather'),
    ('Yağışın.', 'Rain - Open Weather'),
    ('Sıcaklığı göster', 'Temperature - Open Weather'),
    ('Elektriğin son değeri', 'Tesis Toplam Elektrik Tüketimi'),
    ('Isıtma derece gün değeri nedir?', 'Heating degree days - Open Weather'),
    ('What is the latest rain reading?', 'Rain - Open Weather'),
])
def test_inflected_and_capitalized_turkish_subjects_ground(text, expected):
    assert [m.name for m in metric_references(text, METRICS)] == [expected]


def test_unknown_subject_is_not_grounded():
    assert metric_references('Titreşim', METRICS) == []


@pytest.mark.parametrize('text,expected', [
    ('RAIN metriğinin son değeri nedir?', 'RAIN'),
    ('RAIN METRİĞİNİN SON DEĞERİ NEDİR?', 'RAIN'),
    ('GRID IMPORT metriğinin son değeri nedir?', 'GRID IMPORT'),
    ('What is the GRID IMPORT value?', 'GRID IMPORT'),
])
def test_exact_upper_case_english_metric_names_still_ground(text, expected):
    metrics = [ReneryoMetric('r', 'RAIN', 'GAUGE', 'PRECIPITATION'),
               ReneryoMetric('g', 'GRID IMPORT', 'COUNTER', 'ENERGY')]
    assert [m.name for m in metric_references(text, metrics)] == [expected]


def test_mixed_case_request_keeps_upper_case_english_words():
    assert normalize_phrase('RAIN metriğinin son değeri') == 'rain metriğinin son değeri'
