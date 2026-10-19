"""Operation/subject contracts across deterministic and accepted semantic routes."""
from dataclasses import replace
from unittest.mock import Mock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.reneryo_models import ReneryoMetric
from skill.services.conversation_state import DialogueState
from skill.services.futuregen import match_metric, metric_references
from skill.services.semantic_resolver import SemanticAction, SemanticResolution
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_factory_questions import Source, date
from tests.test_services.test_finding_collection_dialogue import _message


class Inventory(Source):
    async def list_metrics(self):
        return [*await super().list_metrics(),
                ReneryoMetric('t', 'Temperature - Open Weather', 'GAUGE', 'TEMPERATURE', 17.5, date(2020, 7)),
                ReneryoMetric('h', 'Humidity - Open Weather', 'GAUGE', 'RATE', .6, date(2020, 7))]


def skill_with_proposal(action, slots=None):
    skill = harness(Inventory())
    skill._semantic_resolver = Mock()
    skill._semantic_resolver.resolve.return_value = SemanticResolution(
        action, 'en-US', .99, .1, slots=slots or {})
    return skill


@pytest.mark.parametrize('text,language', [
    ('What type of metric is Tesis Toplam Elektrik Tüketimi?', 'en-US'),
    ('Elektrik metriğinin türü nedir?', 'tr-TR'),
    ('Which unit does the production metric have?', 'en-US'),
    ('Üretim metriğinin birim grubunu göster.', 'tr-TR'),
    ('What kind of metric is humidity?', 'en-US'),
    ('Nem metriğinin tipi ne?', 'tr-TR'),
])
def test_attributes_select_grounded_detail_before_inventory_keywords(text, language):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text, language), allow_semantic=False)
    assert response(skill)['response_type'] == 'metrics'
    assert len(response(skill)['evidence_rows']) == 1
    assert not skill._futuregen_service.reneryo.calls
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize('text,language', [
    ('Show the current temperature value.', 'en-US'),
    ('Dış sıcaklığın son değerini göster.', 'tr-TR'),
    ('What is the latest humidity reading?', 'en-US'),
    ('Nemin güncel değerini göster.', 'tr-TR'),
])
def test_accepted_device_proposal_cannot_replace_explicit_metric_value(text, language):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text, language))
    r = response(skill)
    assert r['response_type'] == 'metrics'
    assert r['evidence_rows'][0]['id'] == ('h' if 'humidity' in text or 'Nemin' in text else 't')
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize('text', ['List the metrics and their types.', 'Which metrics are available?'])
def test_collection_requests_are_not_single_metric_details(text):
    skill = skill_with_proposal(SemanticAction.METRIC_DETAIL)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'metrics'
    assert len(response(skill)['evidence_rows']) == 4


@pytest.mark.parametrize('text', ['Which devices measure electricity?', 'List electricity meters'])
def test_explicit_devices_remain_meter_inventory(text):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'meters'
    assert skill._futuregen_service.reneryo.calls[0][0] == 'meter'


def test_explicit_meter_filter_cannot_substitute_unlinked_electricity_meter():
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message('Which meters measure temperature?'))
    assert response(skill)['response_type'] == 'meters'
    assert response(skill)['evidence_rows'] == []


def test_explicit_metric_outranks_conflicting_semantic_and_retained_subjects():
    skill = skill_with_proposal(SemanticAction.METRIC_DETAIL, {'metric_name': 'electricity'})
    skill._dialogue_state_store.put('collection-session', DialogueState(
        operation='metric_detail', metric_name='Tesis Toplam Üretim Miktarı'))
    assert handle_reneryo_query(skill, _message('Show the current humidity value.'))
    assert response(skill)['evidence_rows'][0]['id'] == 'h'


@pytest.mark.parametrize('text', ['What type of metric is vibration?', 'Show the latest vibration value.'])
def test_unknown_subject_never_inherits_semantic_or_dialogue_metric(text):
    skill = skill_with_proposal(SemanticAction.METRIC_DETAIL, {'metric_name': 'electricity'})
    skill._dialogue_state_store.put('collection-session', DialogueState(
        operation='metric_detail', metric_name='Tesis Toplam Üretim Miktarı'))
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize('text', ['What is its type?', 'And the latest value?', 'Bunun türü ne?', 'Peki son değer?'])
def test_subject_free_attribute_or_value_followup_retains_bound_metric(text):
    skill = skill_with_proposal(SemanticAction.METRIC_DETAIL, {'metric_name': 'Humidity - Open Weather'})
    skill._dialogue_state_store.put('collection-session', DialogueState(
        operation='metric_detail', metric_name='Humidity - Open Weather'))
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'metrics'
    assert response(skill)['evidence_rows'][0]['id'] == 'h'


def test_period_on_conflicting_value_proposal_is_not_dropped():
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message('Show temperature measurements in June 2020.'))
    assert response(skill)['response_type'] == 'trend'
    assert skill._futuregen_service.reneryo.calls[0][:3] == ('t', date(2020, 6), date(2020, 7))


@pytest.mark.parametrize('text', ['What type are temperature and humidity?', 'Show the latest temperature and humidity values.'])
def test_multiple_metric_subjects_clarify_instead_of_selecting_first(text):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.asyncio
async def test_reference_set_narrows_exact_names_but_preserves_legacy_single_match():
    metrics = await Inventory().list_metrics()
    metrics.append(replace(metrics[2], metric_id='indoor', name='Indoor temperature'))
    assert {m.metric_id for m in metric_references('temperature', metrics)} == {'t', 'indoor'}
    assert [m.metric_id for m in metric_references('Temperature - Open Weather', metrics)] == ['t']
    assert len(metric_references('temperature and humidity', metrics)) == 3
    assert match_metric('temperature', metrics).metric_id == 't'
    assert metric_references('Nem değil sıcaklık', metrics)[0].metric_id == 't'


@pytest.mark.parametrize('text,language', [
    ('How many units did the site turn out yesterday?', 'en-US'),
    ('Dün kaç birim üretim yapıldı?', 'tr-TR'),
])
def test_quantity_units_are_not_metric_attribute_requests(text, language):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)['response_type'] == 'unavailable'
    assert not response(skill)['evidence_rows']
    assert skill._futuregen_service.reneryo.calls
