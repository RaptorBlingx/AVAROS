"""A trend keeps its resolved window and aggregation across clarifications and switches.

Equivalence is checked on the Reneryo requests (metric, exact window, aggregation)
and returned values, not only on response text.
"""
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.services.futuregen import FutureGenService
from tests.test_services.test_finding_collection_dialogue import _Skill, _message

UTC = timezone.utc
# Distinct endpoint values per Reneryo resolution make a wrong aggregation visible.
ENDPOINTS = {'MONTHLY': (10.0, 12.0), 'DAILY': (10.0, 30.0), 'HOURLY': (10.0, 15.0)}


class Source:
    def __init__(self):
        self.calls = []

    async def list_metrics(self):
        observed = datetime(2026, 10, 15, 6, tzinfo=UTC)
        return [
            ReneryoMetric('h', 'Humidity - Open Weather', 'GAUGE', 'RATE', .6, observed),
            ReneryoMetric('e', 'Tesis Toplam Elektrik Tüketimi', 'COUNTER', 'ENERGY', 9000, observed),
        ]

    async def metric_values(self, metric_id, start, end, aggregation):
        self.calls.append((metric_id, start, end, aggregation))
        first, last = ENDPOINTS[aggregation]
        return [ReneryoTrendPoint(start, first, 1), ReneryoTrendPoint(end, last, 1)]

    async def recent_metric_values(self, metric, count=12):
        return [], 0


def harness(timezone_name='UTC'):
    skill = _Skill()
    skill.settings_service = SimpleNamespace(get_profile=lambda _: SimpleNamespace(
        extra_settings={'organization_timezones': {'futuregen': timezone_name}},
    ))
    skill._parse_period = TimePeriod.from_natural_language
    skill._futuregen_service = FutureGenService(Source())
    return skill


def turn(skill, text, clock, language='tr-TR'):
    message = _message(text, language)
    message._avaros_request_clock = clock
    before = len(skill.spoken)
    assert handle_reneryo_query(skill, message)
    assert len(skill.spoken) == before + 1
    return skill.spoken[-1][1]['meta']['avaros_response']


def last_call(skill):
    return skill._futuregen_service.reneryo.calls[-1]


NOON = datetime(2026, 10, 20, 12, tzinfo=UTC)


@pytest.mark.parametrize('period,timezone_name', [
    ('Mayıs ile Haziran 2020', 'UTC'),   # counter month range: MONTHLY buckets
    ('Eylül 2026', 'Europe/Istanbul'),   # local window not on UTC days: finer buckets
    ('Eylül 2026', 'UTC'),
])
def test_direct_clarified_and_switched_trends_request_the_same_reneryo_data(period, timezone_name):
    direct = harness(timezone_name)
    expected = turn(direct, f'{period} elektrik eğilimini göster.', NOON)
    expected_call = last_call(direct)

    clarified = harness(timezone_name)
    assert turn(clarified, f'{period} eğilimini göster.', NOON)['response_type'] == 'clarification'
    resumed = turn(clarified, 'Elektrik.', NOON)

    switched = harness(timezone_name)
    turn(switched, f'{period} nem eğilimini göster.', NOON)
    switch = turn(switched, 'Peki elektrik?', NOON)

    for skill, response in ((clarified, resumed), (switched, switch)):
        assert last_call(skill) == expected_call
        assert response['evidence_rows'] == expected['evidence_rows']
        assert response['headline'] == expected['headline']


@pytest.mark.parametrize('timezone_name,before_midnight,after_midnight,first,direct_text,reply,language', [
    ('UTC', datetime(2026, 10, 20, 23, 59, tzinfo=UTC), datetime(2026, 10, 21, 0, 1, tzinfo=UTC),
     'Dün eğilimini göster.', 'Dün nem eğilimini göster.', 'Nem.', 'tr-TR'),
    # Istanbul local midnight is 21:00 UTC: the window is the local day before.
    ('Europe/Istanbul', datetime(2026, 10, 20, 20, 59, tzinfo=UTC), datetime(2026, 10, 20, 21, 1, tzinfo=UTC),
     'Dün eğilimini göster.', 'Dün nem eğilimini göster.', 'Nem.', 'tr-TR'),
    ('Europe/Istanbul', datetime(2026, 10, 20, 20, 59, tzinfo=UTC), datetime(2026, 10, 20, 21, 1, tzinfo=UTC),
     'Show the trend for yesterday.', 'Show the humidity trend for yesterday.', 'Humidity.', 'en-US'),
])
def test_relative_period_keeps_its_original_window_across_midnight(
        timezone_name, before_midnight, after_midnight, first, direct_text, reply, language):
    direct = harness(timezone_name)
    expected = turn(direct, direct_text, before_midnight, language)
    expected_call = last_call(direct)

    skill = harness(timezone_name)
    assert turn(skill, first, before_midnight, language)['response_type'] == 'clarification'
    resumed = turn(skill, reply, after_midnight, language)
    assert last_call(skill) == expected_call
    assert resumed['evidence_rows'] == expected['evidence_rows']
    # The re-resolved window would start one day later.
    assert expected_call[1] < after_midnight.replace(hour=0, minute=0) or timezone_name != 'UTC'


def test_period_named_in_the_reply_replaces_the_kept_window():
    skill = harness()
    turn(skill, 'Dün eğilimini göster.', datetime(2026, 10, 20, 23, 59, tzinfo=UTC))
    turn(skill, 'Eylül 2026 nem.', datetime(2026, 10, 21, 0, 1, tzinfo=UTC))
    direct = harness()
    turn(direct, 'Eylül 2026 nem eğilimini göster.', datetime(2026, 10, 21, 0, 1, tzinfo=UTC))
    assert last_call(skill) == last_call(direct)


def test_switch_keeps_window_and_resolution_after_a_period_follow_up():
    skill = harness('Europe/Istanbul')
    turn(skill, 'Ağustos 2026 nem eğilimini göster.', NOON)
    turn(skill, 'Peki Eylül 2026?', NOON)
    turn(skill, 'Peki elektrik?', NOON)
    direct = harness('Europe/Istanbul')
    turn(direct, 'Eylül 2026 elektrik eğilimini göster.', NOON)
    assert last_call(skill) == last_call(direct)


def test_new_request_after_a_clarification_does_not_inherit_the_pending_window():
    skill = harness()
    turn(skill, 'Eylül 2026 eğilimini göster.', NOON)
    turn(skill, 'Nem eğilimini göster.', NOON)
    direct = harness()
    turn(direct, 'Nem eğilimini göster.', NOON)
    assert last_call(skill) == last_call(direct)
