import os
import time
from pathlib import Path

import pytest

from skill.services.conversation_state import DialogueState
from skill.services.semantic_resolver import SemanticAction, SemanticResolver


class _ConstantEncoder:
    def embed(self, texts):
        return [[1.0, 0.0] for _ in texts]


class _FailingEncoder:
    def embed(self, texts):
        raise RuntimeError("local inference unavailable")


class _SlowEncoder:
    def embed(self, texts):
        time.sleep(0.1)
        return [[1.0, 0.0] for _ in texts]


def test_equal_semantic_scores_are_treated_as_ambiguous():
    resolver = SemanticResolver(
        encoder=_ConstantEncoder(),
        min_confidence=0.5,
        min_margin=0.01,
    )

    result = resolver.resolve(
        "Could you deal with this?",
        state=DialogueState(active_finding_id="finding-1"),
        language="en-US",
    )

    assert result.action is None
    assert result.ambiguous is True
    assert result.reason == "ambiguous"


def test_finding_actions_are_not_available_without_finding_context():
    resolver = SemanticResolver(
        encoder=_ConstantEncoder(),
        min_confidence=0.5,
        min_margin=0.0,
    )

    candidates = resolver._candidate_actions("tell me more", DialogueState())

    assert SemanticAction.FINDING_EXPLAIN not in candidates
    assert SemanticAction.FINDING_PERIOD not in candidates
    assert SemanticAction.FINDINGS_LIST in candidates
    assert SemanticAction.METRIC_DETAIL in candidates


def test_runtime_inference_failure_returns_ambiguity_instead_of_raising():
    resolver = SemanticResolver(encoder=_ConstantEncoder())
    resolver._encoder = _FailingEncoder()

    result = resolver.resolve(
        "Explain the alert",
        state=DialogueState(active_finding_id="finding-1"),
        language="en-US",
    )

    assert result.action is None
    assert result.ambiguous is True
    assert result.reason == "failure"


def test_runtime_inference_timeout_returns_ambiguity_instead_of_blocking():
    resolver = SemanticResolver(
        encoder=_ConstantEncoder(),
        timeout_seconds=0.05,
    )
    resolver._encoder = _SlowEncoder()

    started = time.perf_counter()
    result = resolver.resolve(
        "Explain the alert",
        state=DialogueState(active_finding_id="finding-1"),
        language="en-US",
    )

    assert time.perf_counter() - started < 0.09
    assert result.action is None
    assert result.ambiguous is True
    assert result.reason == "timeout"


_MODEL_PATH = os.environ.get("AVAROS_SEMANTIC_MODEL_PATH", "")
_RUN_MODEL_EVALS = os.environ.get("AVAROS_RUN_SEMANTIC_MODEL_TESTS") == "1"
pytestmark_model = pytest.mark.skipif(
    not _RUN_MODEL_EVALS or not Path(_MODEL_PATH).is_dir(),
    reason="set AVAROS_RUN_SEMANTIC_MODEL_TESTS=1 with the bundled model",
)


@pytest.fixture(scope="module")
def local_resolver():
    if not _RUN_MODEL_EVALS or not Path(_MODEL_PATH).is_dir():
        pytest.skip("local semantic model evaluation is opt-in")
    return SemanticResolver(model_path=_MODEL_PATH, timeout_seconds=5.0)


_FINDING_STATE = DialogueState(
    organization_id="futuregen",
    active_finding_id="finding-1",
    entity_id="resource-1",
    metric_name="Cooling degree days - Open Weather",
    language="en-US",
)


@pytest.mark.parametrize(
    ("utterance", "language", "expected"),
    [
        (
            "Give me the temporal scope of this alert.",
            "en-US",
            SemanticAction.FINDING_PERIOD,
        ),
        (
            "Bu uyarının kapsadığı tarih aralığı nedir?",
            "tr-TR",
            SemanticAction.FINDING_PERIOD,
        ),
        (
            "Interpret the selected alert for me.",
            "en-US",
            SemanticAction.FINDING_EXPLAIN,
        ),
        (
            "Help me understand the selected operational issue.",
            "en-US",
            SemanticAction.FINDING_EXPLAIN,
        ),
        (
            "Seçili uyarının ne anlama geldiğini söyler misin?",
            "tr-TR",
            SemanticAction.FINDING_EXPLAIN,
        ),
        ("What caused the alert?", "en-US", SemanticAction.FINDING_TRIGGER),
        ("Bu uyarıya ne sebep oldu?", "tr-TR", SemanticAction.FINDING_TRIGGER),
        ("Which facts justify the warning?", "en-US", SemanticAction.FINDING_EVIDENCE),
        (
            "Bu uyarıyı destekleyen veriler neler?",
            "tr-TR",
            SemanticAction.FINDING_EVIDENCE,
        ),
        ("What does the alert concern?", "en-US", SemanticAction.FINDING_ENTITY),
        ("Uyarı hangi kaynağı ilgilendiriyor?", "tr-TR", SemanticAction.FINDING_ENTITY),
        ("What issues are currently active?", "en-US", SemanticAction.FINDINGS_LIST),
        ("Şu anda etkin olan sorunları özetle.", "tr-TR", SemanticAction.FINDINGS_LIST),
        (
            "How did the related indicator evolve over the previous month?",
            "en-US",
            SemanticAction.TREND_SHOW,
        ),
        (
            "İlgili göstergenin önceki aydaki değişimi nasıldı?",
            "tr-TR",
            SemanticAction.TREND_SHOW,
        ),
        (
            "Show details for the associated metric.",
            "en-US",
            SemanticAction.METRIC_DETAIL,
        ),
        (
            "İlgili metriğin ayrıntılarını ver.",
            "tr-TR",
            SemanticAction.METRIC_DETAIL,
        ),
    ],
)
@pytestmark_model
def test_contextual_finding_paraphrases(local_resolver, utterance, language, expected):
    result = local_resolver.resolve(
        utterance,
        state=_FINDING_STATE,
        language=language,
    )

    assert result.action is expected, result
    assert result.language == language


@pytest.mark.parametrize(
    ("utterance", "language", "expected"),
    [
        (
            "Which named performance indicators are available?",
            "en-US",
            SemanticAction.METRICS_LIST,
        ),
        (
            "Kullanılabilir ölçüm göstergeleri neler?",
            "tr-TR",
            SemanticAction.METRICS_LIST,
        ),
        ("Show the energy measuring devices.", "en-US", SemanticAction.METERS_LIST),
        (
            "Which monitoring instruments are available for energy use?",
            "en-US",
            SemanticAction.METERS_LIST,
        ),
        ("Elektriği ölçen cihazları listele.", "tr-TR", SemanticAction.METERS_LIST),
        (
            "Enerji kullanımını izleyen donanımlar hangileri?",
            "tr-TR",
            SemanticAction.METERS_LIST,
        ),
        (
            "What statistical models have been saved?",
            "en-US",
            SemanticAction.REGRESSIONS_LIST,
        ),
        (
            "Mevcut tahmin modellerinin envanteri nedir?",
            "tr-TR",
            SemanticAction.REGRESSIONS_LIST,
        ),
        (
            "Describe the fit of the daily model.",
            "en-US",
            SemanticAction.REGRESSION_DETAIL,
        ),
        (
            "Aylık modelin hata ve uyum ayrıntıları nedir?",
            "tr-TR",
            SemanticAction.REGRESSION_DETAIL,
        ),
    ],
)
@pytestmark_model
def test_inventory_and_regression_paraphrases(
    local_resolver, utterance, language, expected
):
    result = local_resolver.resolve(
        utterance,
        state=DialogueState(language=language),
        language=language,
    )

    assert result.action is expected, result


@pytestmark_model
def test_semantic_trend_period_slot_uses_supported_canonical_period(local_resolver):
    result = local_resolver.resolve(
        "How did the related indicator evolve over the previous month?",
        state=_FINDING_STATE,
        language="en-US",
    )

    assert result.action is SemanticAction.TREND_SHOW
    assert result.slots["period"] == "last month"
    assert result.slots["context_metric"] == _FINDING_STATE.metric_name


@pytest.mark.parametrize(
    ("utterance", "language"),
    [("And its trend?", "en-US"), ("Peki eğilimi?", "tr-TR")],
)
@pytestmark_model
def test_short_contextual_trend_does_not_invent_a_period(
    local_resolver, utterance, language
):
    result = local_resolver.resolve(
        utterance,
        state=_FINDING_STATE,
        language=language,
    )

    assert result.action is SemanticAction.TREND_SHOW
    assert "period" not in result.slots
    assert result.slots["context_metric"] == _FINDING_STATE.metric_name


@pytestmark_model
def test_ambiguous_measurement_inventory_requests_clarification(local_resolver):
    result = local_resolver.resolve(
        "What measurements can I inspect?",
        state=DialogueState(language="en-US"),
        language="en-US",
    )

    assert result.action is None
    assert result.ambiguous is True


@pytest.mark.parametrize(
    "utterance",
    [
        "Can you book my flight tomorrow?",
        "What is the weather forecast?",
        "Turn off the factory equipment.",
        "Write me a poem.",
    ],
)
@pytestmark_model
def test_out_of_scope_requests_are_not_mapped_to_factory_actions(
    local_resolver, utterance
):
    result = local_resolver.resolve(
        utterance,
        state=_FINDING_STATE,
        language="en-US",
    )

    assert result.action is None
    assert result.ambiguous is True
