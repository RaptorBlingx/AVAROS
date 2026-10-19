"""F1/F2: grounded history routing and explicit scenario quantities."""
from copy import deepcopy
from unittest.mock import Mock

import pytest

from skill._handlers import _build_whatif_scenario
from skill._reneryo_handlers import handle_reneryo_query
from skill.domain.exceptions import ValidationError
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.reneryo_models import ReneryoMetric, ReneryoTrendPoint
from skill.services.conversation_state import DialogueState
from tests.test_services.test_answer_correctness import harness, response
from tests.test_services.test_factory_questions import Source
from tests.test_services.test_finding_collection_dialogue import _message
from tests.test_services.test_pr71_routing_contracts import make_skill, send


class WeatherSource(Source):
    def __init__(self, *, available=True, values=True):
        super().__init__(values=values)
        self.available = available

    async def list_metrics(self):
        rows = await super().list_metrics()
        if self.available:
            rows += [ReneryoMetric('t', 'Temperature - Open Weather', 'GAUGE', 'TEMPERATURE'),
                     ReneryoMetric('h', 'Humidity - Open Weather', 'GAUGE', 'RATE')]
        return rows

    async def metric_values(self, metric_id, start, end, period):
        self.calls.append((metric_id, start, end, period))
        return ([ReneryoTrendPoint(start, 20, 1),
                 ReneryoTrendPoint(start + (end - start) / 2, 15, 1)]
                if self.values else [])

    async def recent_metric_values(self, metric, count=12):
        return ([], 0)

    async def list_meters(self, start, end):
        self.calls.append(('meter', start, end))
        return await super().list_meters(start, end)


@pytest.mark.parametrize('text,language', [
    ('Sıcaklık geçmişini göster', 'tr-TR'),
    ('Sicaklik gecmisini goster', 'tr-TR'),
    ('Show temperature history', 'en-US'),
    ('Show historical temperature trend', 'en-US'),
    ('Nem geçmişini göster', 'tr-TR'),
])
def test_history_uses_grounded_metric_without_semantic_meter_guess(text, language):
    source = WeatherSource()
    skill = harness(source)
    skill._semantic_resolver = Mock(side_effect=AssertionError('semantic route must not run'))
    message = _message(text, language)
    original = deepcopy((message.data, message.context))
    assert handle_reneryo_query(skill, message, allow_semantic=False)
    assert response(skill)['response_type'] == 'trend'
    assert source.calls[0][0] == ('h' if 'Nem' in text else 't')
    assert source.calls[0][3] == 'DAILY'
    assert not any(c[0] == 'meter' for c in source.calls)
    assert (message.data, message.context) == original


@pytest.mark.parametrize('language,seed,followup', [
    ('tr-TR', 'Sıcaklık geçmişini göster', 'Peki dün?'),
    ('en-US', 'Show temperature history', 'And yesterday?'),
])
def test_history_period_followup_preserves_temperature(language, seed, followup):
    source = WeatherSource()
    skill = harness(source)
    assert handle_reneryo_query(skill, _message(seed, language))
    source.calls.clear()
    assert handle_reneryo_query(skill, _message(followup, language))
    expected = TimePeriod.from_natural_language('yesterday')
    assert response(skill)['response_type'] == 'trend'
    assert source.calls[0][:3] == ('t', expected.start, expected.end)


@pytest.mark.parametrize('available,values,kind', [(False, True, 'unavailable'), (True, False, 'trend')])
def test_unavailable_history_never_substitutes_prior_production(available, values, kind):
    source = WeatherSource(available=available, values=values)
    skill = harness(source)
    skill._dialogue_state_store.put('collection-session', DialogueState(
        operation='factory_history', metric_name='Tesis Toplam Üretim Miktarı',
        period=TimePeriod.today(),
    ))
    assert handle_reneryo_query(skill, _message('Sıcaklık geçmişini göster', 'tr-TR'))
    assert response(skill)['response_type'] == kind
    assert not response(skill)['evidence_rows']
    assert all(c[0] == 't' for c in source.calls)


@pytest.mark.parametrize('text,language', [
    ('List electricity meters', 'en-US'), ('Elektrik sayaçlarını listele', 'tr-TR'),
])
def test_explicit_meter_inventory_keeps_legacy_operation(text, language):
    skill = harness(WeatherSource())
    assert handle_reneryo_query(skill, _message(text, language))
    assert response(skill)['response_type'] == 'meters'


@pytest.mark.parametrize('text,target', [
    ('What if OEE reaches 90 percent for Line 2', 90),
    ('Hat 2 OEE yüzde 90 olursa ne olur', 90),
    ('Hat 2 OEE %90 olursa ne olur', 90),
    ('Hat 2 OEE 90% olursa ne olur', 90),
    ('Hat 2 OEE yuzde 90 olursa ne olur', 90),
    ('Hat 2 OEE yüzde 90,5 olursa ne olur', 90.5),
    ("Hat 2 OEE yüzde 90'a çıkarsa ne olur", 90),
    ('Hat 2 OEE hedefi yüzde 90 olursa ne olur', 90),
])
def test_explicit_target_preserves_numeric_value(text, target):
    skill, _ = make_skill('tr-TR')
    scenario = _build_whatif_scenario(skill, _message(text, 'tr-TR'), text)
    assert scenario.asset_id == 'Line-2' and scenario.target_metric is CanonicalMetric.OEE
    assert scenario.parameters[0].name == 'target_value'
    assert scenario.parameters[0].proposed_value == target


@pytest.mark.parametrize('text,amount', [
    ('What if OEE increases by 10 percent for Line 2', 10),
    ('Hat 2 OEE yüzde 10 artarsa ne olur', 10),
    ('Hat 2 OEE %10 azalırsa ne olur', -10),
    ('Hat 2 OEE yüzde 2,5 artarsa ne olur', 2.5),
    ('Hat 2 OEE senaryosunu simüle et', 5),
    ('Simulate an OEE scenario for Line 2', 5),
])
def test_relative_and_default_scenarios_remain_distinct_from_absolute_target(text, amount):
    skill, _ = make_skill('tr-TR')
    scenario = _build_whatif_scenario(skill, _message(text), text)
    assert scenario.parameters[0].name == 'assumed_kpi_change_percent'
    assert scenario.parameters[0].proposed_value == amount


@pytest.mark.parametrize('language,text', [
    ('tr-TR', 'Hat 2 OEE yüzde90 olursa ne olur'),
    ('en-US', 'What if OEE reaches percent90 for Line 2'),
    ('tr-TR', 'Hat 2 OEE yüzde 90 veya yüzde 95 olursa ne olur'),
    ('en-US', 'What if OEE reaches 90 or 95 percent for Line 2'),
    ('tr-TR', 'Hat 2 OEE 90 olursa ne olur'),
    ('tr-TR', 'Hat 2 OEE yüzde 90,5,2 olursa ne olur'),
    ('tr-TR', 'Hat 2 OEE yüzde 10 değişirse ne olur'),
    ('en-US', 'What if OEE reaches 90kg for Line 2'),
    ('tr-TR', 'Hat 2 OEE yüzde 10kg artarsa ne olur'),
    ('tr-TR', "Hat 2 OEE yüzde 90'a azalırsa ne olur"),
    ('en-US', 'What if OEE reaches 90 and 95 percent for Line 2'),
    ('en-US', 'What if OEE increases by 10-20 percent for Line 2'),
    ('en-US', 'What if OEE reaches ninety and increases by 10 percent for Line 2'),
])
def test_unresolved_quantity_clarifies_before_simulation(language, text):
    skill, _ = make_skill(language)
    skill.dispatcher.simulate_whatif = Mock()
    r = send(skill, text, language)
    assert r['response_type'] == 'clarification'
    assert not r['evidence_rows'] and not r['assumptions']
    skill.dispatcher.simulate_whatif.assert_not_called()
    assert len(skill.spoken) == 1


@pytest.mark.parametrize('target', [-5, 190])
def test_turkish_target_uses_existing_physical_validation(target):
    skill, _ = make_skill('tr-TR')
    text = f'Hat 2 OEE yüzde {target} olursa ne olur'
    with pytest.raises(ValidationError):
        _build_whatif_scenario(skill, _message(text, 'tr-TR'), text)


@pytest.mark.parametrize('language,seed,correction', [
    ('tr-TR', 'Sıcaklık geçmişini göster', 'Nem geçmişini göster'),
    ('en-US', 'Show temperature history', 'Show humidity history'),
])
def test_explicit_history_subject_switch_keeps_new_metric(language, seed, correction):
    source = WeatherSource()
    skill = harness(source)
    assert handle_reneryo_query(skill, _message(seed, language))
    source.calls.clear()
    assert handle_reneryo_query(skill, _message(correction, language))
    assert response(skill)['response_type'] == 'trend'
    assert source.calls[0][0] == 'h'


@pytest.mark.parametrize('asset_name', ['Press 12', 'Pres 12', 'Press-12'])
def test_numeric_asset_name_is_not_an_explicit_scenario_quantity(asset_name):
    from skill.domain.models import Asset
    skill, _ = make_skill('en-US')
    skill._get_asset_registry = lambda: [Asset('Press-7', 'Press 12', 'machine', aliases=['Pres 12'])]
    skill._resolve_asset_id = lambda message: 'Press-7'
    text = f'Simulate an OEE scenario for {asset_name}'
    scenario = _build_whatif_scenario(skill, _message(text), text)
    assert scenario.parameters[0].name == 'assumed_kpi_change_percent'
    assert scenario.parameters[0].proposed_value == 5


def test_ascii_temperature_history_does_not_reuse_production_subject():
    source = WeatherSource()
    skill = harness(source)
    skill._dialogue_state_store.put('collection-session', DialogueState(
        operation='factory_history', metric_name='Tesis Toplam Üretim Miktarı',
        period=TimePeriod.today(),
    ))
    assert handle_reneryo_query(skill, _message('Sicaklik geçmişini göster', 'tr-TR'))
    assert response(skill)['response_type'] == 'trend'
    assert source.calls[0][0] == 't'


@pytest.mark.parametrize('language,text', [
    ('en-US', 'What if OEE reaches 90 percent for Line 2'),
    ('tr-TR', 'Hat 2 OEE yüzde 90 olursa ne olur'),
])
@pytest.mark.parametrize('registered', [False, True])
def test_scenario_entrypoints_keep_target_scope_and_original_request(language, text, registered):
    from skill import AVAROSSkill
    from skill._handlers import handle_metric_query_fallback
    from skill.use_cases.query_dispatcher import QueryDispatcher
    from tests.helpers.stub_adapter import StubAdapter
    from tests.test_services.test_explicit_query_scope import widget_message

    skill, _ = make_skill(language)
    skill.dispatcher = QueryDispatcher(adapter=StubAdapter())
    skill.dispatcher.simulate_whatif = Mock(wraps=skill.dispatcher.simulate_whatif)
    message = widget_message(text, language)
    original = deepcopy((message.data, message.context))
    skill._sync_response_language(message)
    if registered:
        AVAROSSkill._guard_intent_activation(skill, 'whatif.scenario', skill.handle_whatif_scenario)(message)
    else:
        assert handle_metric_query_fallback(skill, message)
    scenario = skill.dispatcher.simulate_whatif.call_args.args[0]
    assert scenario.asset_id == 'Line-2' and scenario.target_metric is CanonicalMetric.OEE
    assert scenario.parameters[0].name == 'target_value'
    assert scenario.parameters[0].proposed_value == 90
    assert response(skill)['response_type'] == 'what_if'
    assert (message.data, message.context) == original
    assert len(skill.spoken) == 1
