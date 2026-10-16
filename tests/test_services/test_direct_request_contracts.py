"""Request classes, not the frozen language challenge, verify shared contracts."""
from unittest.mock import Mock

import pytest

from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import ReneryoMetric
from skill.services.conversation_state import DialogueState
from skill.services.finding_collection import filters_for, is_evaluation_request
from skill.services.futuregen import match_metric
from skill.services.period_resolution import (
    extract_period_phrase,
    unsupported_period_reference,
)
from skill.services.query_scope import entity_scope
from skill.services.request_correction import affirmative_request
from skill.services.semantic_resolver import SemanticAction, SemanticResolution
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_finding_collection_dialogue import _message, _Skill


@pytest.mark.parametrize('modifier', ['for us', 'for the site', 'for the monthly regression', 'in the observations'])
def test_prepositions_do_not_annotate_equipment(modifier):
    assert entity_scope('Show the data ' + modifier) == (False, False)


@pytest.mark.parametrize('subject', ['boiler 7', 'Alpha', 'meter Alpha', 'unconfigured inverter X', 'plant B', 'plant 7'])
def test_explicit_unknown_entities_remain_protected(subject):
    assert entity_scope('Show humidity trend for ' + subject) == (True, True)


@pytest.mark.parametrize('month,number', [('subat', 2), ('mayis', 5), ('agustos', 8), ('eylul', 9), ('kasim', 11), ('aralik', 12)])
def test_ascii_month_contract(month, number):
    text = f'{month} 2020 elektrik tuketimi'
    assert not unsupported_period_reference(text)
    period = TimePeriod.from_natural_language(extract_period_phrase(text))
    assert period.start.month == number and period.end > period.start


@pytest.mark.parametrize('noun', ['sıcaklık', 'sıcaklığı', 'sıcaklığının', 'sicakligin', 'temperature'])
def test_metric_inflections_remain_inventory_linked(noun):
    metrics = [ReneryoMetric('t', 'Temperature', 'GAUGE', 'TEMPERATURE')]
    assert match_metric(f'{noun} geçmişi', metrics).metric_id == 't'
    assert match_metric('döneme göre titreşim', metrics) is None
    assert match_metric(noun, []) is None


@pytest.mark.parametrize('unit', ['liraya', 'liralık', 'TL', 'euros', 'USD'])
def test_currency_qualifiers_never_return_energy(unit):
    skill = harness()
    assert handle_reneryo_query(skill, _message(f'Elektrik kaç {unit} tuttu?', 'tr-TR'))
    assert response(skill)['response_type'] == 'unavailable'
    assert not skill._futuregen_service.reneryo.calls


@pytest.mark.parametrize('text,status,severity', [
    ('no longer active findings', 'RESOLVED', ''),
    ('etkin olmayan bulgular', 'RESOLVED', ''),
    ('yüksek önem derecesindeki bulgular', 'ACTIVE', 'HIGH'),
    ('düşük önem düzeyindeki bulgular', 'ACTIVE', 'LOW'),
])
def test_explicit_collection_filters(text,status,severity):
    f = filters_for(text, DialogueState())
    assert (f.status, f.severity) == (status, severity)


@pytest.mark.parametrize('verb', ['carry out', 'perform', 'run'])
def test_affirmative_english_evaluation_commands(verb):
    assert is_evaluation_request(f'Please {verb} a new MDSP assessment of current data.')
    assert not is_evaluation_request(f'What happens if you {verb} an MDSP assessment?')
    assert not is_evaluation_request(f'Do not {verb} an MDSP assessment.')


@pytest.mark.parametrize('verb', ['çalıştır', 'başlat', 'yap'])
def test_turkish_evaluation_authorization(verb):
    assert is_evaluation_request(f'Güncel verilerde MDSP değerlendirmesi {verb}manı istiyorum.')
    assert not is_evaluation_request(f'MDSP değerlendirmesi {verb}ma.')
    assert not is_evaluation_request(f'MDSP değerlendirmesi nasıl {verb}ılır?')


@pytest.mark.parametrize('supplied', [True,False])
def test_accepted_proposals_have_same_execution_contract(supplied):
    skill = _Skill()
    proposal = SemanticResolution(SemanticAction.METRICS_LIST, 'en-US', .95, .1)
    skill._semantic_resolver = Mock()
    skill._semantic_resolver.resolve.return_value = proposal
    assert handle_reneryo_query(skill, _message('Which quantities can be measured?'),
                               semantic_resolution=proposal if supplied else None)
    assert response(skill)['response_type'] == 'metrics'


def test_correction_retains_enclosing_explicit_period():
    text = 'Haziran 2020 sayaç endeksi değil, elektrik tüketimini göster'
    result = affirmative_request(text)
    assert extract_period_phrase(result) == 'haziran 2020'


def test_humidity_adjective_does_not_match_an_unknown_device():
    metrics = [ReneryoMetric('h', 'Humidity', 'GAUGE', 'RATE')]
    assert match_metric('how humid is it', metrics).metric_id == 'h'
    assert match_metric('humidifier pressure', metrics) is None


def test_inflected_month_range_uses_existing_inclusive_month_contract():
    text = "Ağustos 2020’dan Eylül 2020’ya sıcaklık eğilimi"
    assert not unsupported_period_reference(text)
    period = TimePeriod.from_natural_language(extract_period_phrase(text))
    assert period.start.month == 8 and period.end.month == 10


@pytest.mark.parametrize('verb', ['direction', 'go up', 'go down', 'artmış', 'yükselmiş', 'düşmüş'])
def test_change_operations_do_not_fall_through_to_period_totals(verb):
    from skill.services.factory_questions import classify_factory_question

    request = classify_factory_question(f'electricity Ağustos 2020 ile Eylül 2020 {verb}', DialogueState())
    assert request.kind == 'trend'


@pytest.mark.asyncio
async def test_counter_month_comparison_requests_domain_monthly_buckets():
    from skill.services.futuregen import FutureGenService
    from tests.test_services.test_factory_questions import Source

    source = Source()
    await FutureGenService(source).trend('electricity May to June 2020 trend',
                                       TimePeriod.from_natural_language('May to June 2020'))
    assert source.calls[0][-1] == 'MONTHLY'


@pytest.mark.parametrize('scope', ['organization acme', 'tenant other-company'])
def test_explicit_named_organization_is_not_replaced_by_signed_context(scope):
    assert entity_scope(f'Show findings for {scope}') == (True, True)



def test_deterministic_pass_does_not_claim_an_inventory_paraphrase_as_consumption():
    skill = harness()
    proposal = SemanticResolution(SemanticAction.METRICS_LIST, 'en-US', .95, .1)
    skill._semantic_resolver = Mock()
    skill._semantic_resolver.resolve.return_value = proposal
    message = _message('Which measurements track production?')
    assert not handle_reneryo_query(skill, message, allow_semantic=False)
    assert not skill._futuregen_service.reneryo.calls
    assert handle_reneryo_query(skill, message)
    assert response(skill)['response_type'] == 'metrics'



def test_currency_code_does_not_treat_english_try_as_a_cost_request():
    from skill.services.factory_questions import is_cost_request

    assert is_cost_request('electricity amount in TRY')
    assert not is_cost_request('Try showing electricity consumption')



@pytest.mark.parametrize('modifier', ['previous', 'prior', 'last'])
def test_calendar_month_modifiers_resolve_to_calendar_period(modifier):
    phrase = extract_period_phrase(f'electricity in the {modifier} calendar month')
    assert phrase == 'last month'


@pytest.mark.parametrize('modifier', ['next', 'coming', 'following'])
def test_future_calendar_modifiers_never_fall_through_to_latest(modifier):
    skill = harness()
    assert handle_reneryo_query(skill, _message(f'electricity in the {modifier} calendar month'))
    assert response(skill)['response_type'] == 'clarification'
    assert not skill._futuregen_service.reneryo.calls
