"""Regression tests for DIA trust and safety release blockers."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from skill._handlers import _build_whatif_scenario
from skill._system_handlers import handle_control_turn_off, handle_control_turn_on
from skill.domain.exceptions import AVAROSError, ValidationError
from skill.domain.models import CanonicalMetric
from skill.use_cases.query_dispatcher import QueryDispatcher
from tests.helpers.stub_adapter import StubAdapter


def _message(utterance: str) -> SimpleNamespace:
    return SimpleNamespace(data={"utterance": utterance})


def _whatif_skill(metric: CanonicalMetric) -> Mock:
    skill = Mock()
    skill._resolve_metric_from_utterance.return_value = metric
    skill._resolve_asset_id.return_value = "Line-1"
    return skill


def test_scan_anomalies_fails_when_prevention_is_unavailable() -> None:
    """A missing analytics service must not be reported as a clean scan."""
    dispatcher = QueryDispatcher(adapter=StubAdapter(), prevention_client=None)

    with pytest.raises(AVAROSError) as exc_info:
        dispatcher.scan_anomalies()

    assert exc_info.value.code == "ANOMALY_NOT_CONFIGURED"
    assert "unavailable" in exc_info.value.user_message.lower()


@pytest.mark.parametrize(
    "utterance",
    [
        "what if temperature drops by 10 degrees",
        "what if line pressure increases by 5 percent",
    ],
)
def test_process_parameter_whatif_requires_model(utterance: str) -> None:
    """Process parameters require an explicit validated sensitivity model."""
    with pytest.raises(ValidationError) as exc_info:
        _build_whatif_scenario(
            _whatif_skill(CanonicalMetric.ENERGY_PER_UNIT),
            _message(utterance),
            utterance,
        )

    assert "sensitivity model" in exc_info.value.user_message.lower()


def test_impossible_whatif_reduction_is_rejected() -> None:
    """A 100% or greater KPI reduction is rejected rather than clamped."""
    utterance = "what if scrap rate drops by 200 percent"

    with pytest.raises(ValidationError) as exc_info:
        _build_whatif_scenario(
            _whatif_skill(CanonicalMetric.SCRAP_RATE),
            _message(utterance),
            utterance,
        )

    assert "cannot be reduced" in exc_info.value.user_message.lower()


@pytest.mark.parametrize(
    ("handler", "action"),
    [
        (handle_control_turn_on, "on"),
        (handle_control_turn_off, "off"),
    ],
)
def test_control_handlers_are_read_only_and_do_not_write_state(
    handler,
    action: str,
) -> None:
    """Equipment commands must disclose the boundary and make no writes."""
    skill = Mock()

    handler(skill, _message(f"turn {action} Line-1"))

    spoken = skill.speak.call_args.args[0].lower()
    assert "read-only" in spoken
    assert f"cannot turn equipment {action}" in spoken
    skill._set_power_state.assert_not_called()
    skill.settings_service.set_runtime_state.assert_not_called()
