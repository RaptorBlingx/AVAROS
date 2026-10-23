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

    async def trend(_utterance, period, *, metric=None, allow_history_fallback=True, period_phrase=None):
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


# --- Independent review regressions: a resumed request keeps its structure. ---

def factory_harness():
    from tests.test_services.test_factory_predeployment import harness as predeployment
    return predeployment()


def test_value_clarification_keeps_the_cumulative_reading_not_period_consumption():
    # "Tüketimi" in the metric name must not turn a value request into consumption.
    skill = factory_harness()
    turn(skill, 'Değeri kaç?')
    resumed = turn(skill, 'Elektrik metriği.')
    assert resumed['response_type'] == 'metrics'
    assert '9.000 kWh' in resumed['headline'] and 'birikimli sayaç' in resumed['headline']
    assert 'Synthetic meter' not in resumed['headline'] and '25 kWh' not in resumed['headline']


@pytest.mark.parametrize('first,answer,direct,language', [
    ('Değeri kaç?', 'Nem.', 'Nemin değeri kaç?', 'tr-TR'),
    ('Değeri kaç?', 'Hava sıcaklığı.', 'Hava sıcaklığının değeri kaç?', 'tr-TR'),
    ('Son ölçüm ne zaman kaydedildi?', 'Yağışın.', 'Yağışın son ölçümü ne zaman kaydedildi?', 'tr-TR'),
    ('Eylül 2026 son ölçümü ne zaman?', 'Nem.', 'Eylül 2026 nem son ölçümü ne zaman?', 'tr-TR'),
    ('Eylül 2026 değeri nedir?', 'Nem.', 'Eylül 2026 nem değeri nedir?', 'tr-TR'),
    ('Eylül 2026 eğilimini göster.', 'Sıcaklık.', 'Eylül 2026 sıcaklık eğilimini göster.', 'tr-TR'),
    ('What is the value?', 'Humidity.', 'What is the humidity value?', 'en-US'),
    ('When was the last reading recorded?', 'Rain.', 'When was the last rain reading recorded?', 'en-US'),
])
def test_resumed_answer_matches_the_same_question_asked_directly(first, answer, direct, language):
    resumed_skill, direct_skill = harness(), harness()
    turn(resumed_skill, first, language)
    resumed = turn(resumed_skill, answer, language)
    expected = turn(direct_skill, direct, language)
    assert (resumed['response_type'], resumed['headline']) == (expected['response_type'], expected['headline'])
    assert (resumed_skill._futuregen_service.trend.await_args is None) == (
        direct_skill._futuregen_service.trend.await_args is None)
    if expected['response_type'] == 'trend':
        resumed_call = resumed_skill._futuregen_service.trend.await_args
        direct_call = direct_skill._futuregen_service.trend.await_args
        assert (resumed_call.args[1], resumed_call.kwargs) == (direct_call.args[1], direct_call.kwargs)


def test_historical_timestamp_constraint_survives_the_clarification():
    skill = harness()
    turn(skill, 'Eylül 2026 son ölçümü ne zaman?')
    resumed = turn(skill, 'Nem.')
    # Inventory has only the latest timestamp: never substitute it for September.
    assert resumed['response_type'] == 'unavailable'
    assert '15.10.2026' not in resumed['headline']


@pytest.mark.parametrize('reply,next_reply,language', [
    ('Sıcaklık değil.', 'Nem.', 'tr-TR'),
    ('Sıcaklık olmasın.', 'Nem.', 'tr-TR'),
    ('Not temperature.', 'Humidity.', 'en-US'),
])
def test_negated_subject_reply_is_not_executed_and_still_awaits_the_subject(reply, next_reply, language):
    skill = harness()
    turn(skill, 'Eylül 2026 eğilimini göster.' if language == 'tr-TR' else 'Show the trend for September 2026.', language)
    response = turn(skill, reply, language)
    assert response['response_type'] == 'clarification'
    assert skill._futuregen_service.trend.await_args is None
    resumed = turn(skill, next_reply, language)
    call = skill._futuregen_service.trend.await_args
    assert resumed['response_type'] == 'trend' and call.kwargs['metric'].metric_id == 'h'
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 9)


@pytest.mark.parametrize('reply,language', [('Sıcaklık değil, nem.', 'tr-TR'), ('Not temperature, humidity.', 'en-US')])
def test_negated_reply_with_a_replacement_uses_only_the_replacement(reply, language):
    skill = harness()
    turn(skill, 'Eylül 2026 eğilimini göster.' if language == 'tr-TR' else 'Show the trend for September 2026.', language)
    resumed = turn(skill, reply, language)
    call = skill._futuregen_service.trend.await_args
    assert resumed['response_type'] == 'trend' and call.kwargs['metric'].metric_id == 'h'
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 9)


@pytest.mark.parametrize('reply', ['Sıcaklık ve titreşim.', 'Sıcaklık ve nem.', 'Sıcaklık, nem.'])
def test_multi_subject_reply_asks_for_one_metric_and_keeps_the_request(reply):
    skill = harness()
    turn(skill, 'Eylül 2026 eğilimini göster.')
    response = turn(skill, reply)
    assert response['response_type'] == 'clarification'
    assert skill._futuregen_service.trend.await_args is None
    resumed = turn(skill, 'Sıcaklık.')
    call = skill._futuregen_service.trend.await_args
    assert resumed['response_type'] == 'trend' and call.kwargs['metric'].metric_id == 't'
    assert (call.args[1].start.year, call.args[1].start.month) == (2026, 9)


def test_subject_switch_keeps_the_trend_through_structured_dispatch():
    skill = harness()
    turn(skill, 'Eylül 2026 nem eğilimini göster.')
    before = skill._futuregen_service.trend.await_args
    turn(skill, 'Peki elektrik?')
    call = skill._futuregen_service.trend.await_args
    # The new subject is executed directly; no factory consumption route is entered.
    assert call.kwargs['metric'].metric_id == 'e' and call.args[1] == before.args[1]


@pytest.mark.parametrize('first,answer,direct', [
    ('Eylül 2026 değeri nedir?', 'Elektrik.', 'Eylül 2026 elektrik değeri nedir?'),
    ('Değeri kaç?', 'Elektrik metriği.', 'Elektrik metriğinin değeri kaç?'),
])
def test_resumed_cumulative_counter_reads_match_the_direct_route(first, answer, direct):
    resumed_skill, direct_skill = factory_harness(), factory_harness()
    turn(resumed_skill, first)
    resumed = turn(resumed_skill, answer)
    expected = turn(direct_skill, direct)
    assert (resumed['response_type'], resumed['headline']) == (expected['response_type'], expected['headline'])


def test_period_named_in_the_clarification_answer_is_kept():
    skill = harness()
    turn(skill, 'Son ölçüm ne zaman kaydedildi?')
    resumed = turn(skill, 'Geçen ay nemin.')
    # Only the latest timestamp exists: a dated timestamp abstains.
    assert resumed['response_type'] == 'unavailable'
    assert '15.10.2026' not in resumed['headline']


@pytest.mark.parametrize('question,language,metric_id', [
    ('Dün hava sıcaklığı kaçtı?', 'tr-TR', 't'),
    ('What was the temperature yesterday?', 'en-US', 't'),
    ('Geçen hafta nem kaçtı?', 'tr-TR', 'h'),
])
def test_dated_value_question_never_answers_with_the_latest_observation(question, language, metric_id):
    skill = harness()
    answer = turn(skill, question, language)
    # The latest reading belongs to another period; the dated value is that period's trend.
    assert answer['response_type'] == 'trend', answer['headline']
    call = skill._futuregen_service.trend.await_args
    assert call.kwargs['metric'].metric_id == metric_id
    assert call.args[1].end <= datetime.now(timezone.utc)


@pytest.mark.parametrize('first,follow_up,language', [
    ('Hava sıcaklığı şu an kaç derece?', 'Dün nasıldı?', 'tr-TR'),
    ('Yağış ne kadar?', 'Peki dün?', 'tr-TR'),
    ("What's the temperature right now?", 'And yesterday?', 'en-US'),
    ('What is the latest humidity reading?', 'How was it yesterday?', 'en-US'),
])
def test_period_follow_up_after_a_latest_value_reads_the_same_metric_then(first, follow_up, language):
    skill = harness()
    latest = turn(skill, first, language)
    assert latest['response_type'] == 'metrics'
    metric = state(skill).metric_name
    answer = turn(skill, follow_up, language)
    assert answer['response_type'] == 'trend', answer['headline']
    assert skill._futuregen_service.trend.await_args.kwargs['metric'].name == metric


def test_latest_follow_up_and_new_subject_keep_their_meaning_after_a_value():
    skill = harness()
    turn(skill, 'Hava sıcaklığı şu an kaç derece?')
    # A new subject is a new latest read, not a trend of the previous metric.
    answer = turn(skill, 'Peki nem?')
    assert answer['response_type'] == 'metrics'
    assert skill._futuregen_service.trend.await_count == 0


@pytest.mark.parametrize('text,phrase', [
    # Typed or transcribed without the apostrophe, the year keeps its case ending.
    ('Eylül 2026da kaç kWh elektrik harcadık?', 'eylül 2026'),
    ("Haziran 2026'daki üretim", 'haziran 2026'),
    ('Mayıstan Haziran 2026ya kadar elektrik', 'mayıs 2026 to haziran 2026'),
])
def test_turkish_case_endings_belong_to_the_calendar_expression(text, phrase):
    from skill.services.period_resolution import extract_period_phrase, unsupported_period_reference
    assert extract_period_phrase(text) == phrase
    assert not unsupported_period_reference(text)


def test_period_only_follow_up_with_a_case_ending_keeps_the_subject():
    skill = harness()
    turn(skill, 'Eylül 2026 sıcaklık eğilimini göster.')
    answer = turn(skill, 'Peki Ağustos 2026da?')
    assert answer['response_type'] == 'trend'
    call = skill._futuregen_service.trend.await_args
    assert call.kwargs['metric'].metric_id == 't' and call.args[1].start.month == 8


@pytest.mark.parametrize('follow_up,language', [
    ('Peki ağustos?', 'tr-TR'), ('Peki ağustosta?', 'tr-TR'), ('What about August?', 'en-US'),
])
def test_bare_month_after_a_trend_uses_its_retained_year(follow_up, language):
    skill = harness()
    turn(skill, 'Eylül 2026 sıcaklık eğilimini göster.' if language == 'tr-TR'
         else 'Show the temperature trend for September 2026.', language)
    answer = turn(skill, follow_up, language)
    assert answer['response_type'] == 'trend', answer['headline']
    period = skill._futuregen_service.trend.await_args.args[1]
    assert (period.start.year, period.start.month) == (2026, 8)


@pytest.mark.parametrize('text,language,expected', [
    # A month without a year never becomes a default window.
    ('Haziranda ne kadar elektrik tükettik?', 'tr-TR', 'Hangi yılın ayını'),
    ('Eylülde sıcaklık nasıldı?', 'tr-TR', 'Hangi yılın ayını'),
    # Month counts stay outside the parser contract; the answer says what works instead.
    ('Son üç ayda elektrik tüketimi nasıl bir eğilim gösterdi?', 'tr-TR', 'son 90 gün'),
    ('Show the humidity trend for the last three months.', 'en-US', 'last 90 days'),
])
def test_rejected_period_names_its_reason_and_an_accepted_form(text, language, expected):
    skill = harness()
    answer = turn(skill, text, language)
    assert answer['response_type'] == 'clarification'
    assert expected in answer['headline']
    assert skill._futuregen_service.trend.await_count == 0


@pytest.mark.parametrize('turns,language', [
    (('Eylül 2026 sıcaklık eğilimini göster.', 'Ağustos 2026 ile karşılaştır.'), 'tr-TR'),
    (('Haziran 2026 ile Mayıs 2026 elektrik tüketimini karşılaştır.',), 'tr-TR'),
    (('Compare electricity consumption in May 2026 and June 2026.',), 'en-US'),
])
def test_period_comparison_is_declined_as_such_not_as_missing_equipment(turns, language):
    skill = harness()
    for text in turns:
        answer = turn(skill, text, language)
    assert answer['response_type'] == 'clarification'
    assert ('Dönemleri birbiriyle karşılaştırmayı desteklemiyorum' in answer['headline']
            or "can't compare periods" in answer['headline'])
    assert 'ekipman kapsamını' not in answer['headline'] and 'equipment scope' not in answer['headline']


@pytest.mark.parametrize('first,switch,language,expected', [
    ('Hava sıcaklığı şu an kaç derece?', 'Peki nem?', 'tr-TR', 'Son ölçümde hava nemi %60'),
    ('What is the latest humidity reading?', 'And the temperature?', 'en-US', 'Temperature - Open Weather: 17.5 °C'),
    ('Nemin son ölçümü ne zaman kaydedildi?', 'Peki sıcaklık?', 'tr-TR', 'Hava sıcaklığı için son ölçüm'),
])
def test_subject_switch_after_a_read_keeps_its_view(first, switch, language, expected):
    skill = harness()
    turn(skill, first, language)
    answer = turn(skill, switch, language)
    # Not the metric's type/unit-group description.
    assert answer['headline'].startswith(expected), answer['headline']
    assert 'türünde bir ölçüm' not in answer['headline'] and 'unit group' not in answer['headline']


def test_subject_switch_after_a_description_stays_a_description():
    skill = harness()
    turn(skill, 'Hava nemi metriğinin birimi nedir?')
    assert 'türünde bir ölçüm' in turn(skill, 'Peki sıcaklık?')['headline']


@pytest.mark.parametrize('thanks,language', [
    ('Teşekkürler.', 'tr-TR'), ('Teşekkür ederim.', 'tr-TR'), ('Tamam, sağ ol', 'tr-TR'), ('Thank you!', 'en-US'),
])
def test_thanks_is_acknowledged_and_keeps_the_conversation(thanks, language):
    skill = harness()
    turn(skill, 'Hava sıcaklığı şu an kaç derece?' if language == 'tr-TR' else 'What is the temperature right now?', language)
    answer = turn(skill, thanks, language)
    assert answer['response_type'] == 'information'
    assert answer['headline'].startswith(('Rica ederim', "You're welcome"))
    assert state(skill).metric_name == 'Temperature - Open Weather'


def test_thanks_closes_a_pending_metric_question():
    skill = harness()
    turn(skill, 'Değeri kaç?')
    assert turn(skill, 'Teşekkür ederim.')['headline'].startswith('Rica ederim')
    assert not state(skill).pending_clarification


@pytest.mark.parametrize('question,language,expected', [
    ('Hava kaç derece?', 'tr-TR', 'Son ölçümde hava sıcaklığı 17,5 °C'),
    ('Hava şu an kaç derece?', 'tr-TR', 'Son ölçümde hava sıcaklığı 17,5 °C'),
    ("What's the temperature right now?", 'en-US', 'Temperature - Open Weather: 17.5 °C'),
    ('How warm is it right now?', 'en-US', 'Temperature - Open Weather: 17.5 °C'),
])
def test_everyday_current_temperature_questions_get_the_reading(question, language, expected):
    skill = harness()
    answer = turn(skill, question, language)
    assert answer['response_type'] == 'metrics'
    assert answer['headline'].startswith(expected), answer['headline']
