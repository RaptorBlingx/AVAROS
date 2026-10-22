"""Resumable Turkish clarifications and follow-up ownership in signed dialogue."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.reneryo_models import ReneryoTrend, ReneryoTrendPoint
from tests.test_services.test_finding_collection_dialogue import _Skill, _message
from tests.test_services.test_turkish_vocabulary import METRICS



def harness():
    skill = _Skill()
    service = skill._futuregen_service
    service.metrics = AsyncMock(return_value=METRICS)

    async def trend(_utterance, period, *, metric=None, allow_history_fallback=True):
        points = tuple(
            ReneryoTrendPoint(datetime(2026, 9, day, tzinfo=timezone.utc), value, 24)
            for day, value in ((1, 10.0), (30, 12.0))
        )
        return ReneryoTrend(metric, period.display_name, 'DAILY', points, 'increasing', 20.0,
                            period_start=period.start, period_end=period.end)

    service.trend = AsyncMock(side_effect=trend)
    return skill


def turn(skill, text, language='tr-TR'):
    before = len(skill.spoken)
    assert handle_reneryo_query(skill, _message(text, language))
    assert len(skill.spoken) == before + 1
    return skill.spoken[-1][1]['meta']['avaros_response']


def state(skill):
    return skill._dialogue_state_store.get('collection-session')


@pytest.mark.parametrize('first,answer,language,check', [
    ('Değeri kaç?', 'Nem.', 'tr-TR', lambda r: r['headline'].startswith('Son ölçümde hava nemi %60')),
    ('Son ölçüm ne zaman kaydedildi?', 'Yağışın.', 'tr-TR',
     lambda r: r['headline'].startswith('Yağış miktarı için son ölçüm') and '1,2' not in r['headline']),
    ('Değeri nedir?', 'Yağış miktarı.', 'tr-TR', lambda r: r['headline'].startswith('Son ölçümde yağış miktarı')),
    ('What is the value?', 'Humidity.', 'en-US', lambda r: r['headline'].startswith('Humidity - Open Weather: 60%')),
    ('When was the last reading recorded?', 'Rain.', 'en-US', lambda r: 'latest recorded timestamp' in r['headline']),
])
def test_metric_clarification_answer_resumes_the_original_read(first, answer, language, check):
    skill = harness()
    asked = turn(skill, first, language)
    assert asked['response_type'] == 'clarification'
    assert state(skill).pending_clarification == 'metric'
    resumed = turn(skill, answer, language)
    assert resumed['response_type'] == 'metrics'
    assert check(resumed), resumed['headline']
    assert not state(skill).pending_clarification and not state(skill).pending_operation
    assert skill._futuregen_service.evaluations == 0


def test_trend_clarification_keeps_the_requested_period():
    skill = harness()
    asked = turn(skill, 'Eylül 2026 eğilimini göster.')
    # A request without a subject asks for one; it is not "missing from inventory".
    assert asked['response_type'] == 'clarification'
    resumed = turn(skill, 'Sıcaklık.')
    assert resumed['response_type'] == 'trend'
    call = skill._futuregen_service.trend.await_args
    assert call.kwargs['metric'].metric_id == 't'
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 9)
    assert call.kwargs['allow_history_fallback'] is False


def test_unknown_answer_reasks_and_still_accepts_a_known_subject():
    skill = harness()
    turn(skill, 'Değeri kaç?')
    unknown = turn(skill, 'Titreşim.')
    assert unknown['response_type'] == 'clarification'
    assert unknown['headline'].startswith('Bu adla yapılandırılmış bir metrik bulamadım.')
    assert turn(skill, 'Nem.')['headline'].startswith('Son ölçümde hava nemi')


@pytest.mark.parametrize('reply', ['Teşekkürler.', 'Tamam.', 'Thanks.'])
def test_acknowledgement_drops_the_pending_question_without_naming_it_a_metric(reply):
    skill = harness()
    turn(skill, 'Değeri kaç?')
    response = turn(skill, reply)
    assert 'Bu adla' not in response['headline'] and 'that name' not in response['headline']
    assert not state(skill).pending_operation


def test_new_request_after_clarification_is_not_merged_and_pending_is_single_use():
    skill = harness()
    turn(skill, 'Değeri kaç?')
    trend = turn(skill, 'Nem eğilimini göster.')
    assert trend['response_type'] == 'trend'
    assert skill._futuregen_service.trend.await_args.kwargs['metric'].metric_id == 'h'
    # A later bare subject is a fresh subject switch, never the stale value question.
    assert not state(skill).pending_operation


@pytest.mark.parametrize('follow_up,language,metric_id', [
    ('Peki sıcaklık?', 'tr-TR', 't'),
    ('Ya yağış?', 'tr-TR', 'r'),
    ('And the rain?', 'en-US', 'r'),
])
def test_subject_switch_after_a_trend_keeps_the_trend_and_period(follow_up, language, metric_id):
    skill = harness()
    turn(skill, 'Eylül 2026 nem eğilimini göster.' if language == 'tr-TR'
         else 'Show the humidity trend for September 2026.', language)
    response = turn(skill, follow_up, language)
    assert response['response_type'] == 'trend'
    call = skill._futuregen_service.trend.await_args
    assert call.kwargs['metric'].metric_id == metric_id
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 9)


@pytest.mark.parametrize('period_reply', ['Ağustos 2026.', 'Ağustos 2026 için?', 'Peki Ağustos 2026?'])
def test_bare_period_reply_continues_the_current_trend(period_reply):
    skill = harness()
    turn(skill, 'Eylül 2026 sıcaklık eğilimini göster.')
    response = turn(skill, period_reply)
    assert response['response_type'] == 'trend'
    call = skill._futuregen_service.trend.await_args
    assert call.kwargs['metric'].metric_id == 't'
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 8)


@pytest.mark.parametrize('question', [
    'Ne yapmalıyım?', 'Ne yapmalıyız?', 'Ne yapmamız gerekiyor?', 'Peki ne yapalım?', 'What should I do?',
])
def test_first_person_next_step_questions_reach_the_selected_finding_review(question):
    skill = _Skill()
    turn(skill, 'List active findings.', 'en-US')
    turn(skill, 'Explain the first one.', 'en-US')
    response = turn(skill, question, 'tr-TR' if question[0] != 'W' else 'en-US')
    assert response['response_type'] == 'finding'
    assert state(skill).active_finding_id == 'one'


@pytest.mark.parametrize('question', ['Hava sıcaklığı kaç derece?', 'Hava nemi yüzde kaç?'])
def test_turkish_value_questions_receive_the_value_not_the_metric_description(question):
    response = turn(harness(), question)
    assert response['headline'].startswith('Son ölçümde')
    assert 'anlık ölçüm' not in response['headline']
