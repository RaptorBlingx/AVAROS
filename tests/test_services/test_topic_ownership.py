"""Synthetic request/context ownership contracts, separate from live/audio acceptance."""
from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from skill._reneryo_handlers import handle_reneryo_query, _deterministic_action
from skill.domain.reneryo_models import ReneryoMetric
from skill.services.conversation_state import DialogueState
from skill.services.semantic_resolver import SemanticAction
from tests.test_services.test_finding_collection_dialogue import _Skill, _message

OBSERVED = datetime(2026, 12, 31, 22, 30, tzinfo=timezone.utc)


def harness():
    skill = _Skill()
    service = skill._futuregen_service
    service.metrics = AsyncMock(return_value=[
        ReneryoMetric('humidity', 'Humidity - Open Weather', 'GAUGE', 'RATE', .61, OBSERVED),
        ReneryoMetric('temperature', 'Outdoor temperature', 'GAUGE', 'TEMPERATURE', 17, OBSERVED),
    ])
    service.finding = AsyncMock(side_effect=service.finding)
    return skill


def query(skill, text, language='en-US'):
    message = _message(text, language)
    # Keep the finding-page hint on every turn, just like the real signed widget.
    message.context['reneryo_context'].update(finding_id='one', metric_name='Cooling degree days - Open Weather')
    before = len(skill.spoken)
    assert handle_reneryo_query(skill, message)
    assert len(skill.spoken) == before + 1
    return skill.spoken[-1][1]['meta']['avaros_response']


@pytest.mark.parametrize('language,question', [
    ('en-US', 'When was the latest humidity reading recorded in UTC?'),
    ('en-US', 'What is the timestamp of the latest humidity observation?'),
    ('tr-TR', 'Son nem ölçümü ne zaman kaydedildi?'),
    ('tr-TR', 'En son nem gözleminin kayıt zamanı nedir?'),
])
def test_explicit_timestamp_after_finding_period_uses_requested_metric(language, question):
    skill = harness()
    query(skill, 'Explain this finding.')
    query(skill, 'What period does this finding cover?')
    before = skill._futuregen_service.finding.await_count
    r = query(skill, question, language)
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['id'] == 'humidity'
    assert r['evidence_rows'][0]['observed_at'] == OBSERVED.isoformat()
    assert '%' not in r['headline'] and '61' not in r['headline']
    assert '22:30 UTC' in r['headline']  # fixture org binding is UTC
    assert skill._futuregen_service.finding.await_count == before
    state = skill._dialogue_state_store.get('collection-session')
    assert state.active_finding_id == '' and state.metric_name == 'Humidity - Open Weather'
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize('question', [
    'When was the latest vibration observation recorded?',
    'Son titreşim ölçümü ne zaman kaydedildi?',
])
def test_unresolved_new_subject_never_reuses_selected_finding(question):
    skill = harness()
    query(skill, 'Explain this finding.')
    before = skill._futuregen_service.finding.await_count
    r = query(skill, question)
    assert r['response_type'] == 'clarification'
    assert skill._futuregen_service.finding.await_count == before
    assert not skill._dialogue_state_store.get('collection-session').active_finding_id


@pytest.mark.parametrize('question,expected', [
    ('What period do the meters cover?', SemanticAction.METERS_LIST),
    ('Sayaçların dönem değerlerini listele', SemanticAction.METERS_LIST),
    ('Explain the humidity trend in September 2026', SemanticAction.TREND_SHOW),
    ('Nem eğilimini açıkla', SemanticAction.TREND_SHOW),
    ('Show all available metrics', SemanticAction.METRICS_LIST),
    ('Kayıtlı modelleri listele', SemanticAction.REGRESSIONS_LIST),
])
def test_explicit_operation_precedes_contextual_finding_keywords(question, expected):
    state = DialogueState(operation='finding', active_finding_id='one', metric_name='Cooling degree days')
    assert _deterministic_action(question.casefold(), state) is expected


@pytest.mark.parametrize('question,expected', [
    ('What period does this finding cover?', SemanticAction.FINDING_PERIOD),
    ('When did it happen?', SemanticAction.FINDING_PERIOD),
    ('Bu bulgu hangi dönemi kapsıyor?', SemanticAction.FINDING_PERIOD),
    ('Bu hangi metriği etkiliyor?', SemanticAction.FINDING_ENTITY),
    ('What evidence supports this finding?', SemanticAction.FINDING_EVIDENCE),
])
def test_genuine_finding_followups_still_use_finding_context(question, expected):
    state = DialogueState(operation='finding', active_finding_id='one', metric_name='Humidity')
    assert _deterministic_action(question.casefold(), state) is expected


@pytest.mark.parametrize('reverse', [False, True])
def test_ambiguous_new_timestamp_subject_cannot_depend_on_inventory_order(reverse):
    skill = harness()
    metrics = skill.dispatcher._run_async(skill._futuregen_service.metrics())
    metrics.append(ReneryoMetric('inside', 'Indoor humidity', 'GAUGE', 'RATE', .5, OBSERVED))
    skill._futuregen_service.metrics.return_value = metrics[::-1] if reverse else metrics
    query(skill, 'Explain this finding.')
    calls = skill._futuregen_service.finding.await_count
    r = query(skill, 'When was the latest humidity observation recorded?')
    assert r['response_type'] == 'clarification'
    assert skill._futuregen_service.finding.await_count == calls
    assert not skill._dialogue_state_store.get('collection-session').active_finding_id


def test_explicit_historical_timestamp_is_not_replaced_by_latest_or_finding_window():
    skill = harness()
    query(skill, 'Explain this finding.')
    r = query(skill, 'When was the humidity observation recorded in September 2026?')
    assert r['response_type'] == 'unavailable' and not r['evidence_rows']
    state = skill._dialogue_state_store.get('collection-session')
    assert not state.active_finding_id and state.period is None
    assert query(skill, 'When was it recorded?')['response_type'] == 'clarification'


def test_missing_timestamp_never_becomes_a_value_or_a_zero_time():
    skill = harness()
    skill._futuregen_service.metrics.return_value = [ReneryoMetric('h', 'Humidity', 'GAUGE', 'RATE', .61, None)]
    query(skill, 'Explain this finding.')
    r = query(skill, 'When was the latest humidity observation recorded?')
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['observed_at'] is None
    assert 'no observation timestamp' in r['headline'] and '61' not in r['headline']


def test_inventory_failure_is_claimed_once_without_falling_back_to_the_finding():
    from skill.domain.exceptions import AdapterError
    from skill.services.dia_response import speak_information
    skill = harness()
    query(skill, 'Explain this finding.')
    previous = skill._futuregen_service.finding.await_count
    skill._futuregen_service.metrics.side_effect = AdapterError(message='offline', code='API_ERROR', platform='reneryo')
    def safe_dispatch(_name, action):
        try:
            return action()
        except AdapterError:
            speak_information(skill, 'Source unavailable.', response_type='error')
            return None
    skill._safe_dispatch = safe_dispatch
    r = query(skill, 'When was the latest humidity observation recorded?')
    assert r['response_type'] == 'error'
    assert skill._futuregen_service.finding.await_count == previous
    assert not skill._dialogue_state_store.get('collection-session').active_finding_id


@pytest.mark.parametrize('question', ['When was it recorded?', 'Bu ne zaman kaydedildi?'])
def test_new_signed_organization_never_inherits_another_organization_subject(question):
    skill = harness()
    query(skill, 'Explain this finding.')
    query(skill, 'When was the latest humidity observation recorded?')
    message = _message(question)
    message.context['reneryo_context']['organization_id'] = 'another-organization'
    before = skill._futuregen_service.finding.await_count
    assert handle_reneryo_query(skill, message)
    r = skill.spoken[-1][1]['meta']['avaros_response']
    assert r['response_type'] == 'clarification'
    assert skill._futuregen_service.finding.await_count == before
    assert 'Humidity' not in r['headline']


def test_finding_selection_survives_a_genuine_selection_clarification():
    skill = harness()
    query(skill, 'List active findings.')
    query(skill, 'Explain finding number 9.')
    r = query(skill, 'Explain the first one.')
    assert r['response_type'] == 'finding' and r['evidence_rows'][0]['finding_id'] == 'one'
    r = query(skill, 'Explain the second one.')
    assert r['response_type'] == 'finding' and r['evidence_rows'][0]['finding_id'] == 'two'


def test_grounded_observation_snapshot_survives_resolution_to_narration_handoff():
    skill = harness()
    query(skill, 'Explain this finding.')
    metric = ReneryoMetric('h', 'Humidity', 'GAUGE', 'RATE', .61, OBSERVED)
    skill._futuregen_service.metrics.side_effect = [[metric], RuntimeError('Unexpected inventory rematch')]
    r = query(skill, 'When was the latest humidity observation recorded?')
    assert r['evidence_rows'][0]['id'] == 'h'
    assert r['evidence_rows'][0]['observed_at'] == OBSERVED.isoformat()
    assert skill._futuregen_service.metrics.await_count == 1


@pytest.mark.parametrize('language,question', [
    ('en-US', 'What is the value of the last humidity observation?'),
    ('tr-TR', 'Son nem gözleminin değeri nedir?'),
])
def test_explicit_value_field_is_preserved_when_switching_from_a_finding(language, question):
    skill = harness()
    query(skill, 'Explain this finding.')
    r = query(skill, question, language)
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['id'] == 'humidity'
    assert '%' in r['headline'] and 'latest recorded timestamp' not in r['headline']


@pytest.mark.parametrize('question', ['Değeri kaç?', 'Degeri kac?'])
def test_short_value_question_retains_the_observation_subject(question):
    skill = harness()
    query(skill, 'Son nem ölçümü ne zaman kaydedildi?', 'tr-TR')
    r = query(skill, question, 'tr-TR')
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['id'] == 'humidity'
    assert '%61' in r['headline']


@pytest.mark.parametrize('language,question', [
    ('tr-TR', 'UTC olarak söyle.'), ('en-US', 'In UTC please.'),
])
def test_timezone_only_followup_retains_latest_observation_subject(language, question):
    skill = harness()
    query(skill, 'When was the latest humidity observation recorded?', language)
    r = query(skill, question, language)
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['id'] == 'humidity'
    assert '22:30 UTC' in r['headline']


def test_unknown_value_subject_does_not_inherit_the_last_observation():
    skill = harness()
    query(skill, 'Son nem ölçümü ne zaman kaydedildi?', 'tr-TR')
    r = query(skill, 'Titreşim değeri kaç?', 'tr-TR')
    assert r['response_type'] == 'clarification'


def test_review_timing_question_does_not_become_a_metric_timestamp_request():
    skill = harness()
    query(skill, 'List active findings.')
    query(skill, 'Explain the first one.')
    query(skill, 'Hangi dönemi kapsıyor?', 'tr-TR')
    before = skill._futuregen_service.metrics.await_count
    r = query(skill, 'Ne zaman tekrar kontrol etmeliyim?', 'tr-TR')
    assert r['response_type'] == 'finding'
    assert skill._futuregen_service.metrics.await_count == before
    assert skill._futuregen_service.evaluations == 0


@pytest.mark.parametrize('question,expected', [
    ('Tesis Toplam Üretim Miktarı değişkenli aylık regresyon modelini açıkla.', 'Tesis Toplam Üretim Miktarı-MONTHLY'),
    ('Explain the monthly regression with driver Tesis Toplam Üretim Miktarı.', 'Tesis Toplam Üretim Miktarı-MONTHLY'),
    ('Aylık regresyon modelini açıkla.', None),
    ('Tesis Toplam Üretim Miktarı açıklayıcı değişkenli regresyonu açıkla.', None),
])
def test_regression_selection_combines_current_period_and_driver(question, expected):
    from tests.test_services.test_futuregen_responses import _regression
    skill = harness()
    skill._futuregen_service.regressions = AsyncMock(return_value=[
        _regression('Tesis Toplam Üretim Miktarı', 'DAILY', .5),
        _regression('Tesis Toplam Üretim Miktarı', 'MONTHLY', .2),
        _regression('Cooling degree days', 'MONTHLY', .3),
    ])
    query(skill, 'Günlük regresyon modelini açıkla.', 'tr-TR')
    r = query(skill, question, 'tr-TR')
    assert r['response_type'] == ('regression' if expected else 'clarification')
    if expected:
        assert r['evidence_rows'][0]['id'] == expected
