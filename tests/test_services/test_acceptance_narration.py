"""Independent synthetic acceptance questions; no live data or audio claims."""
from copy import deepcopy
from dataclasses import replace
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from skill._helpers import request_time_format, request_timezone
from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.services.finding_explanation import finding_headline
from skill.services.futuregen import FutureGenService
from skill.services.language import speech_text
from tests.test_services.test_local_observation_time import configured_skill
from tests.test_services.test_finding_collection_dialogue import _message
from tests.test_services.test_reneryo_finding_followups import _recent_gap_finding

UTC = timezone.utc


@pytest.mark.parametrize('language,question', [
    ('en-US', 'How did temperature change last month?'),
    ('tr-TR', 'Geçen ay sıcaklık nasıl değişti?'),
])
@pytest.mark.parametrize('first,last', [(0, 5), (-10, -5), (20, 15), (20, 20), (20, 20.1)])
def test_temperature_answers_use_celsius_endpoints_not_percentages(language, question, first, last):
    skill = configured_skill({'futuregen': 'Europe/Istanbul'})
    metric = ReneryoMetric('temp', 'Temperature - Open Weather', 'GAUGE', 'TEMPERATURE')
    points = [ReneryoTrendPoint(datetime(2026, 8, day, tzinfo=UTC), value, 24)
              for day, value in [(1, first), (2, last)]]
    source = SimpleNamespace(list_metrics=AsyncMock(return_value=[metric]),
                             metric_values=AsyncMock(return_value=points))
    skill._futuregen_service = FutureGenService(source)
    assert handle_reneryo_query(skill, _message(question, language))
    spoken, kwargs = skill.spoken[-1]
    response = kwargs['meta']['avaros_response']
    assert response['response_type'] == 'trend'
    assert '%' not in response['headline'] and 'percent' not in spoken and 'yüzde' not in spoken
    assert '°C' in response['headline'] and ('derece' if language == 'tr-TR' else 'Celsius') in spoken
    assert [row['value'] for row in response['evidence_rows']] == [first, last]
    assert [row['time'] for row in response['evidence_rows']] == [p.timestamp.isoformat() for p in points]
    assert ('no net change' in response['headline'] or 'net değişim yok' in response['headline']) == (first == last)
    assert ('drop' in response['headline'] or 'düşüş' in response['headline']) == (last < first)


@pytest.mark.asyncio
async def test_celsius_has_no_relative_change_even_at_negative_origin():
    metric = ReneryoMetric('temp', 'Temperature', 'GAUGE', 'TEMPERATURE')
    start, end = datetime(2026, 8, 1, tzinfo=UTC), datetime(2026, 8, 3, tzinfo=UTC)
    points = [ReneryoTrendPoint(start, -10, 1), ReneryoTrendPoint(end, -5, 1)]
    source = SimpleNamespace(metric_values=AsyncMock(return_value=points))
    trend = await FutureGenService(source).trend('temperature trend', TimePeriod(start, end, 'test'), metric=metric)
    assert trend.change_percent is None and trend.change_absolute == 5
    assert trend.direction == 'increasing'


@pytest.mark.parametrize('language,question,expected', [
    ('en-US', 'When was the latest humidity reading recorded in UTC?', '22:30 UTC'),
    ('tr-TR', 'Son nem değeri UTC olarak ne zaman kaydedildi?', '22:30 UTC'),
    ('en-US', 'When was the latest humidity recorded, including the time zone?', 'Europe/Istanbul'),
    ('tr-TR', 'Son nem değeri ne zaman kaydedildi, saat dilimi dahil?', 'Europe/Istanbul'),
])
def test_explicit_timezone_details_are_request_scoped(language, question, expected):
    skill = configured_skill({'futuregen': 'Europe/Istanbul'})
    observed = datetime(2026, 12, 31, 22, 30, tzinfo=UTC)
    metric = ReneryoMetric('humidity', 'Humidity', 'GAUGE', 'RATE', .94, observed)
    skill._futuregen_service = FutureGenService(SimpleNamespace(list_metrics=AsyncMock(return_value=[metric])))
    message = _message(question, language)
    assert request_timezone(skill, message) == 'Europe/Istanbul'
    assert handle_reneryo_query(skill, message)
    response = skill.spoken[-1][1]['meta']['avaros_response']
    assert expected in response['headline']
    assert response['evidence_rows'][0]['observed_at'] == observed.isoformat()
    assert request_time_format(skill, _message('When was humidity recorded?')) == {
        'timezone_name': 'Europe/Istanbul', 'include_timezone': False,
    }


@pytest.mark.parametrize('language', ['en-US', 'tr-TR'])
def test_gap_overlap_is_explained_without_clipping_or_mutating_source(language):
    # Artificial gap crosses the start of an artificial 30-day evaluation window.
    finding = _recent_gap_finding()
    evidence = deepcopy(finding.evidence)
    evidence.update(recentGapCount=1, affectedResourceCount=1)
    evidence['longestGap'] = {'start': '2026-08-31T18:00:00Z',
                             'end': '2026-09-01T18:17:00Z', 'durationSeconds': 87420}
    finding = replace(finding, evidence=evidence,
                      evaluation_start=datetime(2026, 9, 1, tzinfo=UTC),
                      evaluation_end=datetime(2026, 10, 1, tzinfo=UTC))
    before = deepcopy(finding)
    period = finding_headline(finding, '', language, action='finding.period', timezone_name='Europe/Istanbul')
    headline = finding_headline(finding, '', language)
    details = finding_headline(finding, '', language, action='finding.evidence', timezone_name='Europe/Istanbul')
    assert ('24 saat 17 dakika' if language == 'tr-TR' else '24 hours 17 minutes') in period
    assert ('önce olabilir' if language == 'tr-TR' else 'may start before') in period
    assert ('21:00' in period and '21:17' in period and '03:00' in period)
    assert 'Europe/Istanbul' not in period and 'UTC' not in speech_text(period, language)
    assert ('nedeni henüz belirlenmiş değil' if language == 'tr-TR' else 'cause is unconfirmed') in headline
    if language == 'en-US':
        assert 'a significant data gap in 1 OpenWeather resource.' in headline
        assert '1 recent significant gap per resource' in details
        assert '1 OpenWeather resource.' in details
        assert '1 gaps' not in details
    assert finding == before


def test_widget_utterance_array_honors_explicit_utc_without_changing_org_zone():
    skill = configured_skill({'futuregen': 'Europe/Istanbul'})
    message = _message('unused')
    message.data = {'utterances': ['Show humidity history yesterday in UTC']}
    assert request_time_format(skill, message) == {'timezone_name': 'UTC', 'include_timezone': True}
    assert request_timezone(skill, message) == 'Europe/Istanbul'


def test_utc_is_a_presentation_qualifier_and_unknown_equipment_stays_unresolved():
    from skill.services.query_scope import entity_scope
    assert entity_scope('Show humidity in UTC') == (False, False)
    assert entity_scope('Show humidity in unknown-compressor UTC')[1]


@pytest.mark.parametrize('language', ['en-US', 'tr-TR'])
@pytest.mark.parametrize('rule,evidence,expected', [
    ('regression-model-fit-quality', {'rSquared': .2, 'normalizedRmsePct': 30},
     ('intended use needs review', 'amaçlanan kullanımına uygunluğu incelenmeli')),
    ('regression-driver-cadence-compatibility', {'period': 'DAILY', 'incompatibleDrivers': [
        {'name': 'Monthly production', 'fastestCadenceSeconds': 2592000}]},
     ('appropriate model period needs review', 'uygun model dönemi incelenmeli')),
    ('regression-primary-model-availability', {'seuId': 'opaque-private-id', 'resultCount': 1},
     ('1 eligible saved regression result,', '1 kayıtlı uygun regresyon sonucu')),
])
def test_finding_meaning_uses_verified_rule_semantics_without_schedule_or_id_leaks(language, rule, evidence, expected):
    finding = replace(_recent_gap_finding(), rule_id=rule, evidence=evidence)
    answer = finding_headline(finding, '', language)
    assert expected[language == 'tr-TR'] in answer
    assert 'opaque-private-id' not in answer
    assert 'runs more frequently' not in answer and 'daha sık çalış' not in answer
    assert finding.evidence == evidence
