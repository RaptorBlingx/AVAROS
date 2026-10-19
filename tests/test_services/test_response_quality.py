"""Presentation guards: base-unit semantics, evidence and material assumptions."""
from datetime import datetime, timezone, timedelta

import pytest

from skill.services.futuregen_responses import format_reneryo_value, metric_detail_headline
from skill.domain.reneryo_models import ReneryoMetric
from skill.services.language import format_observation_time, period_display_name


@pytest.mark.parametrize('value,group,tr,en', [
    (59645.93, 'ENERGY', '59.645,93 kWh', '59,645.93 kWh'),
    (.94, 'RATE', '%94', '94%'),
    (0, 'RATE', '%0', '0%'),
    (1.2, 'RATE', '%120', '120%'),  # no clipping or inferred percentage scale
    (17.5, 'TEMPERATURE', '17,5 °C', '17.5 °C'),
    (13849, 'PIECE', '13.849 adet', '13,849 units'),
    (1, 'PIECE', '1 adet', '1 unit'),
    (.000002, 'ENERGY', '0,000002 kWh', '0.000002 kWh'),
])
def test_reneryo_units_are_localized_without_losing_scale(value, group, tr, en):
    assert format_reneryo_value(value, group, 'tr-TR') == tr
    assert format_reneryo_value(value, group, 'en-US') == en


def test_unknown_group_does_not_gain_a_known_unit():
    text = format_reneryo_value(42, 'CUSTOM', 'tr-TR')
    assert text == '42 CUSTOM'
    assert 'kWh' not in text and '%' not in text


def test_observation_time_converts_offset_before_labelling_utc():
    value = datetime(2026, 10, 15, 13, 11, tzinfo=timezone(timedelta(hours=3)))
    assert format_observation_time(value, 'tr-TR') == '15.10.2026 10:11 UTC'
    assert format_observation_time(value.replace(tzinfo=None), 'tr-TR') == '15.10.2026 13:11'


def test_metric_source_record_and_value_stay_unchanged():
    metric = ReneryoMetric('h', 'Humidity - Open Weather', 'GAUGE', 'RATE', .94,
                          datetime(2026, 10, 15, 10, 11, tzinfo=timezone.utc))
    assert '%94' in metric_detail_headline(metric, 'tr-TR')
    assert '94%' in metric_detail_headline(metric, 'en-US')
    assert metric.last_value == .94 and metric.metric_id == 'h'
    assert 'Hava nemi' in metric_detail_headline(metric, 'tr-TR')
    assert metric.name == 'Humidity - Open Weather'


def test_historical_fallback_label_does_not_leak_english():
    text = period_display_name('available monthly history 2020-05 – 2020-06', 'tr-TR')
    assert text == 'mevcut aylık geçmiş Mayıs 2020 – Haziran 2020'


def test_simple_value_answer_keeps_counter_boundary_and_observation_date():
    metric = ReneryoMetric('e', 'Electricity', 'COUNTER', 'ENERGY', 1000,
                          datetime(2026, 10, 15, 6, tzinfo=timezone.utc))
    tr = metric_detail_headline(metric, 'tr-TR', value_only=True)
    assert '1.000 kWh' in tr and '15.10.2026 06:00 UTC' in tr
    assert 'birikimli sayaç' in tr and 'dönem tüketimi' in tr
    assert 'kaynak grubu' not in tr


def test_turkish_scenario_states_absolute_target_and_material_confidence():
    from skill.domain.models import CanonicalMetric
    from skill.domain.results import WhatIfResult
    from skill.services.response_builder import TurkishResponseBuilder
    result = WhatIfResult(scenario_name='target', target_metric=CanonicalMetric.OEE,
                          baseline=57.2, projected=90, delta=32.8, delta_percent=57.34,
                          confidence=.45, factors={'target_value': 90}, unit='%')
    text = TurkishResponseBuilder().format_whatif_result(result)
    assert 'hedef değer yüzde 90' in text and 'güven düzeyi düşük' in text
    assert 'gelebilir' in text and '57,3' in text


@pytest.mark.parametrize('label,expected', [('Mayis 2026', 'Mayıs 2026'),
                                            ('eylul 2026', 'Eylül 2026'),
                                            ('haziran 2020', 'Haziran 2020')])
def test_system_period_labels_use_turkish_month_spelling(label, expected):
    assert period_display_name(label, 'tr-TR') == expected


def test_turkish_widget_scenario_metadata_uses_same_typed_assumption():
    from unittest.mock import Mock
    from skill.domain.models import CanonicalMetric
    from skill.domain.results import WhatIfResult
    from skill.services.response_builder import TurkishResponseBuilder
    from skill.services.dia_response import speak_with_evidence
    result = WhatIfResult(scenario_name='target', target_metric=CanonicalMetric.OEE,
                          baseline=80, projected=90, delta=10, delta_percent=12.5,
                          confidence=.65, factors={'target_value': 90}, unit='%')
    skill = Mock(_response_language='tr-TR', response_builder=TurkishResponseBuilder())
    speak_with_evidence(skill, skill.response_builder.format_whatif_result(result), result)
    meta = skill.speak.call_args.kwargs['meta']['avaros_response']
    assert meta['assumptions'] == ['Varsayım: hedef değer yüzde 90.']
    assert meta['warnings'] == ['Bu aritmetik senaryo karar desteği içindir; nedensel bir model değildir.']
    assert [r['value'] for r in meta['evidence_rows']] == [80, 90]
    assert [r['label'] for r in meta['evidence_rows']] == ['Başlangıç', 'Senaryo']
