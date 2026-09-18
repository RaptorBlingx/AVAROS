from dataclasses import dataclass, field
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import skill._reneryo_handlers as handlers
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
    )


def _resolution(action, *, margin=0.03):
    return SemanticResolution(
        action=action,
        language="en-US",
        confidence=0.88,
        margin=margin,
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


def test_specific_non_broad_intent_never_invokes_semantic_resolver(monkeypatch):
    skill = _skill(_resolution(SemanticAction.TREND_SHOW))
    delegated = Mock(return_value=True)
    monkeypatch.setattr(handlers, "handle_reneryo_query", delegated)

    handled = handlers.try_arbitrate_legacy_intent(
        skill, _Message("compare line one and line two"), "compare.energy"
    )

    assert handled is False
    skill._semantic_resolver.resolve.assert_not_called()


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
    assert delegated.call_args.kwargs["semantic_resolution"].action is SemanticAction.FINDING_EXPLAIN


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
    assert delegated.call_args.kwargs["semantic_resolution"].action is SemanticAction.METRIC_DETAIL


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
