"""Shared metric operation and explicit inventory-filter contracts."""
from dataclasses import replace

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.services.semantic_resolver import SemanticAction
from tests.test_services.test_answer_correctness import response
from tests.test_services.test_finding_collection_dialogue import _message
from tests.test_services.test_operation_metric_grounding import (
    Inventory,
    skill_with_proposal,
)


@pytest.mark.parametrize('action', [SemanticAction.METERS_LIST, SemanticAction.METRICS_LIST])
@pytest.mark.parametrize('text,language', [
    ('Nemin kayıtlı son ölçümünü getir.', 'tr-TR'),
    ('Give me the latest humidity reading.', 'en-US'),
])
def test_inventory_proposals_cannot_replace_specific_value_requests(action, text, language):
    skill = skill_with_proposal(action)
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)['evidence_rows'][0]['id'] == 'h'
    assert len(response(skill)['evidence_rows']) == 1


@pytest.mark.parametrize('text,metric', [
    ('Explain the electricity metric.', 'e'),
    ('Describe the humidity indicator.', 'h'),
    ('Elektrik metriğini açıkla.', 'e'),
    ('Nem göstergesini anlat.', 'h'),
])
def test_single_metric_subject_is_detail_without_exact_definition_verbs(text, metric):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert [e['id'] for e in response(skill)['evidence_rows']] == [metric]


@pytest.mark.parametrize('text,ids', [
    ('Which electricity metrics are available?', {'e'}),
    ('Hangi elektrik metrikleri mevcut?', {'e'}),
    ('List humidity indicators.', {'h'}),
    ('Sıcaklık ve nem metriklerini listele.', {'t','h'}),
    ('List all metrics.', {'e','p','t','h'}),
    ('Mevcut metrikleri listele.', {'e','p','t','h'}),
])
def test_collection_filters_use_inventory_membership_without_changing_operation(text, ids):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    r = response(skill)
    assert {e['id'] for e in r['evidence_rows']} == ids
    assert 'metric' in r['response_type']
    # A one-member catalogue is still narrated as a catalogue, not a value answer.
    assert 'related metric' not in r['headline']


@pytest.mark.parametrize('text', ['List vibration metrics.', 'Titreşim metriklerini listele.',
                                  'Which rain metrics are available?', 'List metrics for vibration.'])
def test_unresolved_explicit_filter_cannot_return_full_inventory(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'


@pytest.mark.parametrize('text', ['Explain the vibration metric.', 'Titreşim metriğini açıkla.'])
def test_unconfigured_detail_subject_cannot_be_substituted(text):
    skill = skill_with_proposal(SemanticAction.METRIC_DETAIL, {'metric_name': 'electricity'})
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'


@pytest.mark.parametrize('text', ['What quantities do we have measurements for?',
                                  'What measurements are currently available?'])
def test_generic_measurement_inventory_is_not_forced_to_an_unnamed_value(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert len(response(skill)['evidence_rows']) == 4


def test_family_inventory_can_return_multiple_members_without_first_match_bias():
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    source = Inventory()
    original = source.list_metrics
    async def metrics():
        rows = await original()
        return rows + [replace(rows[2], metric_id='indoor', name='Indoor temperature')]
    source.list_metrics = metrics
    skill._futuregen_service.reneryo = source
    assert handle_reneryo_query(skill, _message('List temperature metrics.'))
    assert {e['id'] for e in response(skill)['evidence_rows']} == {'t', 'indoor'}


@pytest.mark.parametrize('text', ['List electricity and vibration metrics.',
                                  'Elektrik ve titreşim metriklerini listele.'])
def test_known_subject_cannot_hide_an_unresolved_collection_modifier(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'


@pytest.mark.parametrize('text', ['List Tesis Toplam Elektrik Tüketimi metrics.',
                                  'Show available named indicators.',
                                  'List electricity consumption metrics.'])
def test_source_names_and_catalogue_qualifiers_are_not_new_filter_domains(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'metrics'


@pytest.mark.parametrize('action', [SemanticAction.FINDINGS_EVALUATE, SemanticAction.FINDING_EXPLAIN])
@pytest.mark.parametrize('text', ['Give me the latest humidity reading.', 'Nemin güncel değerini getir.'])
def test_concrete_read_fields_outrank_unrelated_semantic_action_proposals(action, text):
    skill = skill_with_proposal(action)
    assert handle_reneryo_query(skill, _message(text))
    assert [e['id'] for e in response(skill)['evidence_rows']] == ['h']
    skill._semantic_resolver.resolve.assert_not_called()


@pytest.mark.parametrize('text', ['Show the latest vibration value.', 'Titreşimin son değerini göster.',
                                  'Show vibration measurements in June 2020.',
                                  'Haziran 2020 titreşim ölçümlerini göster.'])
def test_an_unbound_value_subject_cannot_turn_into_generic_inventory(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert response(skill)['response_type'] == 'clarification'


@pytest.mark.parametrize('text', [
    'Hiçbir değerlendirme çalıştırma; metrikleri listele.',
    'Do not evaluate anything; list the metrics.',
])
def test_filter_validation_preserves_request_clause_boundaries(text):
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message(text))
    assert len(response(skill)['evidence_rows']) == 4


@pytest.mark.asyncio
async def test_punctuation_in_a_source_owned_metric_name_is_not_a_clause_boundary():
    from skill._reneryo_handlers import _has_inventory_modifier
    rows = await Inventory().list_metrics()
    rows[2] = replace(rows[2], name='Outdoor; Temperature')
    assert not _has_inventory_modifier('List Outdoor; Temperature metrics.', rows)
    assert _has_inventory_modifier('List electricity metrics; vibration metrics.', rows)


@pytest.mark.parametrize('text,language', [
    ('Show the available electricity indicators.', 'en-US'),
    ('Mevcut elektrik göstergelerini getir.', 'tr-TR'),
])
def test_collection_noun_contract_precedes_factory_amount_routing(text, language):
    skill = skill_with_proposal(SemanticAction.METERS_LIST)
    assert handle_reneryo_query(skill, _message(text, language))
    assert [e['id'] for e in response(skill)['evidence_rows']] == ['e']
    assert not skill._futuregen_service.reneryo.calls


def test_quantity_operation_still_owns_an_indicator_reading_question():
    skill = skill_with_proposal(SemanticAction.METRICS_LIST)
    assert handle_reneryo_query(skill, _message('How much electricity did the electricity indicator record in June 2020?'))
    assert response(skill)['response_type'] == 'information'
    assert skill._futuregen_service.reneryo.calls
