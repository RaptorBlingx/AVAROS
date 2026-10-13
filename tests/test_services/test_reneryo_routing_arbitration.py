from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import skill._handlers as fallback_handlers
import skill._reneryo_handlers as handlers
import skill.services.dia_dialogue as dialogue
from skill.services.conversation_state import DialogueStateStore
from skill.services.dia_dialogue import is_browser_message
from skill.services.semantic_resolver import SemanticAction, SemanticResolution


@dataclass
class _Message:
    utterance: str
    confidence: float = 0.9
    signed: bool = True
    data: dict = field(init=False)
    context: dict = field(init=False)

    def __post_init__(self):
        self.data = {
            "utterance": self.utterance,
            "__intent__": {"confidence": self.confidence},
        }
        self.context = {
            "session": {"session_id": "session-1", "lang": "en-US"},
            "reneryo_context": (
                {"organization_id": "futuregen", "language": "en-US"}
                if self.signed
                else {}
            ),
        }


def _skill(resolution):
    resolver = Mock()
    resolver.resolve.return_value = resolution
    return SimpleNamespace(
        _loaded_profile="reneryo",
        _response_language="en-US",
        _dialogue_state_store=DialogueStateStore(),
        _semantic_resolver=resolver,
        _extract_utterance_text=lambda message: message.data["utterance"],
        _get_asset_registry=list,
        settings_service=None,
    )


def _resolution(action, *, margin=0.03, language="en-US", ambiguous=False):
    return SemanticResolution(
        action=action,
        language=language,
        confidence=0.88,
        margin=margin,
        ambiguous=ambiguous,
    )


def test_exact_registered_legacy_utterance_keeps_fast_path(monkeypatch):
    skill = _skill(_resolution(SemanticAction.FINDINGS_LIST))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("what can you do"), "help.capabilities.list"
    )

    assert handled is False
    skill._semantic_resolver.resolve.assert_not_called()
    delegated.assert_not_called()


def test_specific_comparison_validates_scope_without_semantic_resolver(monkeypatch):
    skill = _skill(_resolution(SemanticAction.TREND_SHOW))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)
    structured = Mock(return_value=True)
    monkeypatch.setattr(handlers, "try_handle_scoped_query", structured)

    message = _Message("compare line one and line two")
    handled = handlers.try_arbitrate_legacy_intent(skill, message, "compare.energy")

    assert handled is True
    skill._semantic_resolver.resolve.assert_not_called()
    structured.assert_called_once_with(skill, message)


def test_signed_broad_help_match_can_route_to_contextual_finding(monkeypatch):
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN))
    skill._dialogue_state_store.put(
        "session-1",
        handlers.DialogueState(active_finding_id="finding-1"),
    )
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill,
        _Message("Help me understand the selected operational issue."),
        "help",
    )

    assert handled is True
    delegated.assert_called_once()
    assert delegated.call_args.kwargs == {"allow_semantic": False}


@pytest.mark.parametrize(
    ("utterance", "language"),
    [
        ("Help me understand this selected issue.", "en-US"),
        ("Bu seçili uyarıyı anlamama yardım et.", "tr-TR"),
    ],
)
def test_active_finding_arbitrates_broad_help_to_explanation(
    monkeypatch, utterance, language
):
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN, language=language))
    skill._dialogue_state_store.put(
        "session-1",
        handlers.DialogueState(active_finding_id="finding-1"),
    )
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(skill, _Message(utterance), "help")

    assert handled is True
    assert delegated.call_args.kwargs == {"allow_semantic": False}


def test_active_metric_arbitrates_broad_help_to_metric_detail(monkeypatch):
    skill = _skill(_resolution(SemanticAction.METRIC_DETAIL))
    skill._dialogue_state_store.put(
        "session-1", handlers.DialogueState(metric_name="Cooling degree days"),
    )
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("Tell me about this indicator."), "help.capabilities.list"
    )

    assert handled is True
    assert (
        delegated.call_args.kwargs["semantic_resolution"].action
        is SemanticAction.METRIC_DETAIL
    )


def test_explicit_help_without_reneryo_context_keeps_capabilities_fast_path(monkeypatch):
    skill = _skill(_resolution(SemanticAction.FINDINGS_LIST))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("What can you do?"), "help"
    )

    assert handled is False
    skill._semantic_resolver.resolve.assert_not_called()
    delegated.assert_not_called()


def test_ambiguous_contextual_help_clarifies_instead_of_using_capabilities(monkeypatch):
    skill = _skill(_resolution(None, ambiguous=True, language="tr-TR"))
    skill._dialogue_state_store.put(
        "session-1",
        handlers.DialogueState(active_finding_id="finding-1"),
    )
    message = _Message("Peki bununla ilgili ne var?")
    message.context["reneryo_context"]["language"] = "tr-TR"
    clarification = Mock()
    monkeypatch.setattr(handlers, "_semantic_clarification", clarification)

    handled = handlers.try_arbitrate_legacy_intent(skill, message, "help")

    assert handled is True
    clarification.assert_called_once_with(skill, "tr-TR")


def test_broad_asset_match_can_route_to_reneryo_meter_inventory(monkeypatch):
    skill = _skill(_resolution(SemanticAction.METERS_LIST))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill,
        _Message("Which monitoring instruments are available for energy use?"),
        "list.assets",
    )

    assert handled is True
    delegated.assert_called_once()


def test_first_turn_metric_detail_is_allowed_to_request_metric_name(monkeypatch):
    skill = _skill(_resolution(SemanticAction.METRIC_DETAIL))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill,
        _Message("Give me details about a performance indicator."),
        "kpi.energy.total",
    )

    assert handled is True
    assert (
        delegated.call_args.kwargs["semantic_resolution"].action
        is SemanticAction.METRIC_DETAIL
    )


def test_missing_metric_uses_targeted_bilingual_clarification(monkeypatch):
    spoken = Mock()
    monkeypatch.setattr(handlers, "speak_information", spoken)
    rows = [SimpleNamespace(name="Electricity"), SimpleNamespace(name="Production")]

    handlers._metric_clarification(SimpleNamespace(), rows, "tr-TR")

    assert "Hangi Reneryo metriğini" in spoken.call_args.args[1]
    assert spoken.call_args.kwargs["response_type"] == "clarification"
    assert spoken.call_args.kwargs["suggestions"] == [
        "Electricity metriğini açıkla",
        "Production metriğini açıkla",
    ]


@pytest.mark.parametrize("signed", [False])
def test_arbitration_requires_signed_organization_context(monkeypatch, signed):
    skill = _skill(_resolution(SemanticAction.FINDINGS_LIST))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("Summarize the current issues", signed=signed), "help"
    )

    assert handled is False
    skill._semantic_resolver.resolve.assert_not_called()
    delegated.assert_not_called()


def test_weak_semantic_disagreement_clarifies_instead_of_misrouting(monkeypatch):
    skill = _skill(_resolution(SemanticAction.METRICS_LIST, margin=0.002))
    delegated = Mock(return_value=True)
    clarification = Mock()
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)
    monkeypatch.setattr(handlers, "_semantic_clarification", clarification)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("Tell me something useful"), "help"
    )

    assert handled is True
    delegated.assert_not_called()
    clarification.assert_called_once_with(skill, "en-US")


@pytest.mark.parametrize(
    "utterance",
    [
        "Help me understand this selected issue.",
        "Bu bulgunun kanıtlarını açıkla.",
        "Tell me something useful.",
        "Book a flight tomorrow.",
    ],
)
def test_signed_embedded_widget_is_eligible_for_semantic_fallback(utterance):
    """The real widget reaches fallback; resolver still owns action/clarity."""
    message = _Message(utterance)
    message.context.update(
        {
            "source": "avaros-widget",
            "platform": "AVAROS-Widget-v1",
            "reneryo_widget_session_validated": True,
        }
    )

    assert is_browser_message(message) is True


def test_signed_hivemind_widget_fallback_ping_is_eligible():
    """HiveMind rewrites source while retaining proxy-authenticated context."""
    message = _Message("Help me understand this selected issue.")
    message.context.update(
        {
            "source": "avaros-client::1::avaros-client::session-1",
            "platform": "AVAROS-Widget-v1",
            "reneryo_widget_session_validated": True,
        }
    )

    assert is_browser_message(message) is True


def test_embedded_widget_identifiers_alone_do_not_grant_fallback_eligibility():
    message = _Message("Help me understand this selected issue.", signed=False)
    message.context.update(
        {
            "source": "avaros-widget",
            "platform": "AVAROS-Widget-v1",
            "reneryo_widget_session_validated": True,
        }
    )

    assert is_browser_message(message) is False


def test_legacy_web_ui_eligibility_is_unchanged():
    message = _Message("Tell me something useful.", signed=False)
    message.context["source"] = "avaros-web-ui"

    assert is_browser_message(message) is True


@pytest.mark.parametrize(
    "utterance",
    [
        "Help me understand this selected issue.",
        "Bu seçili bulguyu anlamama yardım et.",
    ],
)
def test_structured_capabilities_path_arbitrates_signed_finding_context(
    monkeypatch, utterance
):
    """Exercise the live parser -> CAPABILITIES -> arbitration dispatch path."""
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN))
    message = _Message(utterance)
    message.context["reneryo_context"]["finding_id"] = "finding-1"
    delegated = Mock(return_value=True)
    capabilities = Mock()
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)
    monkeypatch.setattr(dialogue, "_handle_capabilities", capabilities)

    handled = dialogue.try_handle_structured_query(skill, message)

    assert handled is True
    delegated.assert_called_once_with(skill, message)
    capabilities.assert_not_called()


def test_structured_explicit_capabilities_keeps_capabilities_with_context(monkeypatch):
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN))
    message = _Message("What can you do?")
    message.context["reneryo_context"]["finding_id"] = "finding-1"
    delegated = Mock(return_value=True)
    capabilities = Mock()
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)
    monkeypatch.setattr(dialogue, "_handle_capabilities", capabilities)

    handled = dialogue.try_handle_structured_query(skill, message)

    assert handled is True
    delegated.assert_not_called()
    capabilities.assert_called_once_with(skill, message)


def test_structured_turkish_capabilities_keeps_capabilities_with_context(monkeypatch):
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN, language="tr-TR"))
    message = _Message("Neler yapabilirsin?")
    message.context["reneryo_context"].update(
        {"finding_id": "finding-1", "language": "tr-TR"}
    )
    delegated = Mock(return_value=True)
    capabilities = Mock()
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)
    monkeypatch.setattr(dialogue, "_handle_capabilities", capabilities)

    handled = dialogue.try_handle_structured_query(skill, message)

    assert handled is True
    delegated.assert_not_called()
    capabilities.assert_called_once_with(skill, message)


def test_structured_turkish_capabilities_uses_current_signed_turn_language(
    monkeypatch,
):
    skill = _skill(_resolution(SemanticAction.FINDING_EXPLAIN, language="tr-TR"))
    message = _Message("Neler yapabilirsin?")
    message.context.update(
        {
            "reneryo_widget_session_validated": True,
            "reneryo_context": {
                "organization_id": "futuregen",
                "language": "tr-TR",
            },
        }
    )
    spoken = Mock()
    skill.speak = spoken

    handled = dialogue.try_handle_structured_query(skill, message)

    assert handled is True
    assert "Future Gen için sayaçları" in spoken.call_args.args[0]
    assert spoken.call_args.kwargs["meta"]["language"] == "tr-TR"


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("Show the first electricity trend", SemanticAction.TREND_SHOW),
        ("Show the electricity trend for last month", SemanticAction.TREND_SHOW),
        ("Üretim eğilimini son 30 gün için göster", SemanticAction.TREND_SHOW),
        ("Why is the monthly regression weak?", SemanticAction.REGRESSION_DETAIL),
        ("Explain the second finding", SemanticAction.FINDING_EXPLAIN),
        ("What should we do about this finding?", SemanticAction.FINDING_NEXT_REVIEW),
    ],
)
def test_structured_layer_defers_explicit_signed_reneryo_requests(
    monkeypatch, utterance, expected
):
    skill = _skill(_resolution(expected))
    state = handlers.DialogueState(
        active_finding_id="finding-1",
        finding_ids=("finding-1", "finding-2"),
        operation="finding",
        selected_finding_from_collection=True,
    )
    skill._dialogue_state_store.put("session-1", state)
    message = _Message(utterance)
    message.context["reneryo_widget_session_validated"] = True
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    assert handlers._deterministic_action(handlers.normalize_phrase(utterance), state) is expected
    assert dialogue.try_handle_structured_query(skill, message) is True
    delegated.assert_called_once_with(skill, message, allow_semantic=False)


def test_signed_widget_semantics_precede_generic_structured_fallback(monkeypatch):
    message = _Message("Give me an overview of current operational alerts.")
    message.context["reneryo_widget_session_validated"] = True
    skill = SimpleNamespace(
        _extract_utterance_text=lambda current: current.data["utterance"],
        _is_anomaly_query=lambda _text: False,
        _is_drift_query=lambda _text: False,
        _is_forecast_query=lambda _text: False,
        _is_whatif_query=lambda _text: False,
    )
    reneryo = Mock(side_effect=[False, True])
    structured = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", reneryo)
    monkeypatch.setattr(fallback_handlers, "try_handle_structured_query", structured)

    handled = fallback_handlers.handle_metric_query_fallback(skill, message)

    assert handled is True
    assert reneryo.call_count == 2
    assert reneryo.call_args_list[0].kwargs == {"allow_semantic": False}
    structured.assert_not_called()


def test_explicit_turkish_capabilities_precede_semantic_fallback(monkeypatch):
    message = _Message("Neler yapabilirsin?")
    message.context["reneryo_widget_session_validated"] = True
    skill = SimpleNamespace(
        _extract_utterance_text=lambda current: current.data["utterance"],
        _is_anomaly_query=lambda _text: False,
        _is_drift_query=lambda _text: False,
        _is_forecast_query=lambda _text: False,
        _is_whatif_query=lambda _text: False,
    )
    reneryo = Mock(return_value=False)
    structured = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", reneryo)
    monkeypatch.setattr(fallback_handlers, "try_handle_structured_query", structured)

    handled = fallback_handlers.handle_metric_query_fallback(skill, message)

    assert handled is True
    reneryo.assert_called_once_with(skill, message, allow_semantic=False)
    structured.assert_called_once_with(skill, message, include_simple_kpi=True)


def test_widget_identifiers_without_proxy_marker_do_not_get_priority(monkeypatch):
    message = _Message("Give me an overview of current operational alerts.")
    message.context.update({"source": "avaros-widget", "platform": "AVAROS-Widget-v1"})
    skill = SimpleNamespace(
        _extract_utterance_text=lambda current: current.data["utterance"],
        _is_anomaly_query=lambda _text: False,
        _is_drift_query=lambda _text: False,
        _is_forecast_query=lambda _text: False,
        _is_whatif_query=lambda _text: False,
    )
    reneryo = Mock(return_value=False)
    structured = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", reneryo)
    monkeypatch.setattr(fallback_handlers, "try_handle_structured_query", structured)

    handled = fallback_handlers.handle_metric_query_fallback(skill, message)

    assert handled is True
    reneryo.assert_called_once_with(skill, message, allow_semantic=False)
    structured.assert_called_once()


def test_recent_metric_context_beats_retained_finding_for_trend_followup():
    state = handlers.DialogueState(
        active_finding_id="finding-1",
        metric_name="Cooling degree days - Open Weather",
        operation="trend",
    )

    action = handlers._deterministic_action(
        handlers.normalize_phrase("Peki bu metrik son 30 günde nasıl değişti?"),
        state,
    )

    assert action is SemanticAction.TREND_SHOW


def test_recent_regression_context_reuses_selected_model_for_fit_followup():
    state = handlers.DialogueState(
        entity_id="daily-model",
        operation="regression_detail",
    )

    action = handlers._deterministic_action(
        handlers.normalize_phrase("What is its fit quality?"),
        state,
    )

    assert action is SemanticAction.REGRESSION_DETAIL


@pytest.mark.parametrize(
    "utterance",
    [
        "Which electricity measuring devices are configured?",
        "Tesisteki elektrik ölçüm cihazlarını özetler misin?",
    ],
)
def test_physical_measurement_device_language_routes_to_meters(utterance):
    action = handlers._deterministic_action(
        handlers.normalize_phrase(utterance), handlers.DialogueState()
    )

    assert action is SemanticAction.METERS_LIST


def test_saved_predictive_model_inventory_routes_to_regressions():
    action = handlers._deterministic_action(
        handlers.normalize_phrase(
            "What predictive models have been saved for this factory?"
        ),
        handlers.DialogueState(),
    )

    assert action is SemanticAction.REGRESSIONS_LIST


def test_turkish_supporting_facts_route_to_finding_evidence():
    action = handlers._deterministic_action(
        handlers.normalize_phrase("Bu bulguyu destekleyen gerçekler neler?"),
        handlers.DialogueState(active_finding_id="finding-1"),
    )

    assert action is SemanticAction.FINDING_EVIDENCE


def test_turkish_course_word_routes_to_trend():
    action = handlers._deterministic_action(
        handlers.normalize_phrase(
            "Soğutma derece günlerinin son dört haftadaki seyrini göster."
        ),
        handlers.DialogueState(),
    )

    assert action is SemanticAction.TREND_SHOW


@pytest.mark.parametrize(
    ("utterance", "expected"),
    [
        ("What does this finding mean?", SemanticAction.FINDING_EXPLAIN),
        ("What should we do about this finding?", SemanticAction.FINDING_NEXT_REVIEW),
        ("What should we do about this regression finding?", SemanticAction.FINDING_NEXT_REVIEW),
        ("Bu bulguyu incele", SemanticAction.FINDING_EXPLAIN),
        ("Why is the monthly regression weak?", SemanticAction.REGRESSION_DETAIL),
        ("Regresyon modelinin eğitim dönemi nedir?", SemanticAction.REGRESSION_DETAIL),
        ("Show electricity trend", SemanticAction.TREND_SHOW),
        ("Show the first electricity trend", SemanticAction.TREND_SHOW),
        ("Geçen ay için soğutma derece gün eğlimini göster.", SemanticAction.TREND_SHOW),
    ],
)
def test_selected_finding_does_not_steal_followups_or_topic_changes(
    utterance, expected
):
    state = handlers.DialogueState(
        active_finding_id="finding-1",
        metric_name="Humidity - Open Weather",
        operation="finding",
        finding_ids=("finding-1", "finding-2"),
        selected_finding_from_collection=True,
    )

    assert (
        handlers._deterministic_action(handlers.normalize_phrase(utterance), state)
        is expected
    )


def test_signed_handoff_does_not_restore_prior_metric_after_topic_change():
    skill = _skill(_resolution(SemanticAction.METRIC_DETAIL))
    skill._dialogue_state_store.put(
        "session-1",
        handlers.DialogueState(
            metric_name="Tesis Toplam Elektrik Tüketimi", operation="trend"
        ),
    )
    message = _Message("Not humidity, electricity")
    message.context["reneryo_context"]["metric_name"] = "Humidity - Open Weather"

    assert (
        handlers._context_state(skill, message).metric_name
        == "Tesis Toplam Elektrik Tüketimi"
    )
