"""Local multilingual semantic routing for unresolved AVAROS requests.

The resolver classifies an utterance into an allow-listed canonical action. It
never answers a domain question and never receives raw Reneryo or MDSP data.
"""

from __future__ import annotations

import logging
import os
import re
from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from threading import RLock
from typing import Any, Protocol

from skill.services.conversation_state import DialogueState
from skill.services.language import normalize_phrase
from skill.services.period_resolution import extract_period_phrase

LOGGER = logging.getLogger(__name__)

MODEL_NAME = "avaros/multilingual-e5-small-int8"
MODEL_SOURCE = "Xenova/multilingual-e5-small"
DEFAULT_MODEL_PATH = "/opt/avaros/models/multilingual-e5-small"


class SemanticAction(str, Enum):
    """Actions the semantic layer may request from deterministic executors."""

    FINDING_EXPLAIN = "finding.explain"
    FINDING_TRIGGER = "finding.trigger"
    FINDING_EVIDENCE = "finding.evidence"
    FINDING_PERIOD = "finding.period"
    FINDING_ENTITY = "finding.entity"
    FINDINGS_LIST = "findings.list"
    METRICS_LIST = "metrics.list"
    METRIC_DETAIL = "metric.detail"
    METERS_LIST = "meters.list"
    TREND_SHOW = "trend.show"
    REGRESSIONS_LIST = "regressions.list"
    REGRESSION_DETAIL = "regression.detail"


@dataclass(frozen=True)
class SemanticResolution:
    """Constrained output returned by local semantic classification."""

    action: SemanticAction | None
    language: str
    confidence: float = 0.0
    margin: float = 0.0
    ambiguous: bool = False
    slots: dict[str, str] = field(default_factory=dict)
    reason: str = ""

    @property
    def accepted(self) -> bool:
        return self.action is not None and not self.ambiguous


class EmbeddingEncoder(Protocol):
    """Minimal embedding interface used by the resolver and tests."""

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        """Return normalized vectors for every input text."""


_ACTION_DESCRIPTIONS: dict[SemanticAction, tuple[str, ...]] = {
    SemanticAction.FINDING_EXPLAIN: (
        "Meaning and explanation of the selected finding for operations.",
        "Seçili bulgunun operasyonlar açısından anlamı ve açıklaması.",
        "Interpret or summarize what the selected alert means.",
        "Seçili uyarının ne anlama geldiğini yorumla veya özetle.",
    ),
    SemanticAction.FINDING_TRIGGER: (
        "Cause and trigger condition of the selected finding; why the rule fired.",
        "Seçili bulgunun nedeni ve tetiklenme koşulu; kuralın neden çalıştığı.",
        "Explain why the selected alert happened and which threshold was met.",
        "Seçili uyarının neden oluştuğunu ve hangi eşiğin aşıldığını açıkla.",
    ),
    SemanticAction.FINDING_EVIDENCE: (
        "Evidence, measurements, and supporting facts for the selected finding.",
        "Seçili bulgunun kanıtları, ölçümleri ve destekleyici verileri.",
        "Facts or data that justify and support the selected warning.",
        "Seçili uyarıyı doğrulayan ve destekleyen gerçekler veya veriler.",
    ),
    SemanticAction.FINDING_PERIOD: (
        "Time period, evaluation window, or dates covered by the selected finding.",
        "Seçili bulgunun dönemi, değerlendirme aralığı veya kapsadığı tarihler.",
        "When the selected alert happened or was evaluated; its date range.",
        "Seçili uyarının ne zaman oluştuğu veya değerlendirildiği; tarih aralığı.",
        "Temporal scope and start or end dates of the selected alert.",
        "Seçili uyarının zamansal kapsamı ile başlangıç veya bitiş tarihleri.",
    ),
    SemanticAction.FINDING_ENTITY: (
        "Affected entity: the resource, metric, meter, or model concerned by the selected finding.",
        "Etkilenen varlık: seçili bulgunun ilgili olduğu kaynak, metrik, sayaç veya model.",
        "Which subject, resource, or item the selected alert concerns.",
        "Seçili uyarının hangi konuyu, kaynağı veya öğeyi ilgilendirdiği.",
    ),
    SemanticAction.FINDINGS_LIST: (
        "Inventory and summary of active decision-support findings, issues, or alerts.",
        "Etkin karar destek bulgularının, sorunların veya uyarıların listesi ve özeti.",
        "Show all current operational issues and decision-support alerts.",
        "Mevcut operasyonel sorunların ve karar destek uyarılarının tümünü göster.",
    ),
    SemanticAction.METRICS_LIST: (
        "Inventory and summary of available Reneryo metrics, measurements, and indicators.",
        "Mevcut Reneryo metriklerinin, ölçümlerinin ve göstergelerinin listesi ve özeti.",
        "Show the available named indicators and measured variables.",
        "Mevcut adlı göstergeleri ve ölçülen değişkenleri göster.",
    ),
    SemanticAction.METRIC_DETAIL: (
        "Details and current metadata for the one related metric in session context.",
        "Oturum bağlamındaki tek bir ilgili metriğin ayrıntıları ve güncel meta verileri.",
        "Continue from the finding to its related indicator, without asking for a trend.",
        "Eğilim istemeden bulgudan ilgili göstergeye geç.",
    ),
    SemanticAction.METERS_LIST: (
        "Inventory and summary of available energy and electricity meters or measuring devices.",
        "Mevcut enerji ve elektrik sayaçlarının veya ölçüm cihazlarının listesi ve özeti.",
        "Show the physical devices that meter electricity or energy consumption.",
        "Elektrik veya enerji tüketimini ölçen fiziksel cihazları göster.",
    ),
    SemanticAction.TREND_SHOW: (
        "Metric trend, evolution, or change over time for a requested period or related contextual metric.",
        "İstenen dönemde veya bağlamdaki ilgili metriğin zaman içindeki eğilimi, gelişimi veya değişimi.",
        "How a related indicator rose, fell, or developed during a time range.",
        "İlgili bir göstergenin bir zaman aralığında nasıl arttığı, azaldığı veya değiştiği.",
    ),
    SemanticAction.REGRESSIONS_LIST: (
        "Inventory and summary of all saved regression analysis models as a group.",
        "Kayıtlı tüm regresyon analizi modellerinin toplu listesi ve özeti.",
        "Show every available saved statistical model, not one model's details.",
        "Belirli bir modelin ayrıntısı yerine mevcut kayıtlı istatistiksel modellerin tümünü göster.",
        "Existence and availability of multiple saved models as an inventory.",
        "Birden fazla kayıtlı modelin mevcut olduğu toplu envanter.",
    ),
    SemanticAction.REGRESSION_DETAIL: (
        "Details of one saved regression model: drivers, period, fit, error, and training dates.",
        "Belirli bir kayıtlı regresyon modelinin ayrıntıları: sürücüler, dönem, uyum, hata ve eğitim tarihleri.",
        "Explain one model's quality, variables, frequency, error, or training range.",
        "Bir modelin kalitesini, değişkenlerini, sıklığını, hatasını veya eğitim aralığını açıkla.",
        "Describe the fit quality of one daily or monthly regression model.",
        "Tek bir günlük veya aylık regresyon modelinin uyum kalitesini açıkla.",
    ),
}

_OUT_OF_SCOPE_DESCRIPTIONS = (
    "Unsupported general conversation, greeting, small talk, or unrelated question.",
    "Desteklenmeyen genel sohbet, selamlama veya ilgisiz bir soru.",
    "Travel, booking, personal advice, or another request outside Reneryo data.",
    "Seyahat, rezervasyon, kişisel tavsiye veya Reneryo verileri dışındaki başka bir istek.",
    "A command to control equipment or change factory data rather than read it.",
    "Ekipmanı kontrol etme veya fabrika verisini okumak yerine değiştirme komutu.",
    "A general weather forecast question, not a saved Reneryo metric trend.",
    "Kayıtlı bir Reneryo metrik eğilimi değil, genel hava tahmini sorusu.",
    "A request to write creative content, a poem, story, or unrelated document.",
    "Şiir, hikâye veya ilgisiz bir belge gibi yaratıcı içerik yazma isteği.",
)

_CONFUSABLE_ACTION_PAIRS = {
    frozenset({SemanticAction.METRICS_LIST, SemanticAction.METERS_LIST}): 0.012,
}

_FINDING_ACTIONS = frozenset(
    {
        SemanticAction.FINDING_EXPLAIN,
        SemanticAction.FINDING_TRIGGER,
        SemanticAction.FINDING_EVIDENCE,
        SemanticAction.FINDING_PERIOD,
        SemanticAction.FINDING_ENTITY,
    }
)


class FastEmbedEncoder:
    """Pinned, local ONNX multilingual E5 encoder."""

    _registration_lock = RLock()
    _registered = False

    def __init__(self, *, model_path: str, threads: int = 2) -> None:
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType

        path = Path(model_path)
        if not path.is_dir():
            raise FileNotFoundError(f"Semantic model directory does not exist: {path}")
        with self._registration_lock:
            if not self.__class__._registered:
                try:
                    TextEmbedding.add_custom_model(
                        model=MODEL_NAME,
                        pooling=PoolingType.MEAN,
                        normalization=True,
                        sources=ModelSource(hf=MODEL_SOURCE),
                        dim=384,
                        model_file="onnx/model_int8.onnx",
                        description="Local multilingual E5-small INT8 semantic router",
                        license="mit",
                        size_in_gb=0.13,
                    )
                except ValueError as exc:
                    if "already registered" not in str(exc):
                        raise
                self.__class__._registered = True
        self._model = TextEmbedding(
            model_name=MODEL_NAME,
            specific_model_path=str(path),
            threads=max(1, threads),
        )

    def embed(self, texts: Iterable[str]) -> list[list[float]]:
        return [vector.tolist() for vector in self._model.embed(list(texts))]


class SemanticResolver:
    """Map unresolved bilingual utterances to constrained AVAROS actions."""

    def __init__(
        self,
        *,
        encoder: EmbeddingEncoder | None = None,
        model_path: str | None = None,
        min_confidence: float = 0.80,
        min_margin: float = 0.003,
        timeout_seconds: float = 0.75,
        threads: int = 2,
    ) -> None:
        self._encoder = encoder or FastEmbedEncoder(
            model_path=model_path or DEFAULT_MODEL_PATH,
            threads=threads,
        )
        self._min_confidence = min(max(min_confidence, 0.0), 1.0)
        self._min_margin = min(max(min_margin, 0.0), 1.0)
        self._timeout_seconds = max(0.05, timeout_seconds)
        self._executor = ThreadPoolExecutor(
            max_workers=1, thread_name_prefix="semantic-router"
        )
        self._action_vectors = self._embed_catalog(_ACTION_DESCRIPTIONS)
        self._out_of_scope_vectors = self._encoder.embed(
            [f"passage: {description}" for description in _OUT_OF_SCOPE_DESCRIPTIONS]
        )

    @classmethod
    def from_environment(cls) -> SemanticResolver | None:
        enabled = os.environ.get("AVAROS_SEMANTIC_ROUTING_ENABLED", "true")
        if enabled.strip().lower() not in {"1", "true", "yes", "on"}:
            return None
        try:
            return cls(
                model_path=os.environ.get(
                    "AVAROS_SEMANTIC_MODEL_PATH", DEFAULT_MODEL_PATH
                ),
                min_confidence=float(
                    os.environ.get("AVAROS_SEMANTIC_MIN_CONFIDENCE", "0.80")
                ),
                min_margin=float(os.environ.get("AVAROS_SEMANTIC_MIN_MARGIN", "0.003")),
                timeout_seconds=float(
                    os.environ.get("AVAROS_SEMANTIC_TIMEOUT_SECONDS", "0.75")
                ),
                threads=int(os.environ.get("AVAROS_SEMANTIC_THREADS", "2")),
            )
        except Exception as exc:  # noqa: BLE001 - optional local fallback
            LOGGER.warning("Local semantic resolver unavailable: %s", exc)
            return None

    def resolve(
        self,
        utterance: str,
        *,
        state: DialogueState,
        language: str,
    ) -> SemanticResolution:
        """Resolve within a hard latency bound; ambiguity is never guessed."""
        text = utterance.strip()
        if not text:
            return SemanticResolution(None, language, ambiguous=True, reason="empty")
        future = self._executor.submit(self._resolve_sync, text, state, language)
        try:
            return future.result(timeout=self._timeout_seconds)
        except TimeoutError:
            future.cancel()
            LOGGER.warning(
                "Local semantic resolution exceeded %.2fs", self._timeout_seconds
            )
            return SemanticResolution(None, language, ambiguous=True, reason="timeout")
        except Exception as exc:  # noqa: BLE001 - graceful fallback is required
            LOGGER.warning("Local semantic resolution failed: %s", exc)
            return SemanticResolution(None, language, ambiguous=True, reason="failure")

    def _resolve_sync(
        self, utterance: str, state: DialogueState, language: str
    ) -> SemanticResolution:
        if _is_vague_contextual_followup(utterance, state):
            return SemanticResolution(
                None, language, ambiguous=True, reason="vague_context"
            )
        vector = self._encoder.embed([f"query: {utterance}"])[0]
        candidates = self._candidate_actions(utterance, state)
        ranked = sorted(
            (
                (
                    action,
                    max(
                        _dot(vector, anchor) for anchor in self._action_vectors[action]
                    ),
                )
                for action in candidates
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked:
            return SemanticResolution(
                None, language, ambiguous=True, reason="no_candidates"
            )
        action, confidence = ranked[0]
        action_runner_up = ranked[1][1] if len(ranked) > 1 else 0.0
        out_of_scope = max(
            _dot(vector, anchor) for anchor in self._out_of_scope_vectors
        )
        runner_up = max(action_runner_up, out_of_scope)
        margin = confidence - runner_up
        required_margin = self._min_margin
        if len(ranked) == 1:
            # A bounded context or an explicit domain cue can constrain the
            # allow-list to one action. Still require it to beat out-of-scope,
            # but do not apply the general multi-action separation margin.
            required_margin = 0.0
        else:
            required_margin = max(
                required_margin,
                _CONFUSABLE_ACTION_PAIRS.get(
                    frozenset({action, ranked[1][0]}), required_margin
                ),
            )
        ambiguous = confidence < self._min_confidence or margin < required_margin
        slots: dict[str, str] = {}
        if action is SemanticAction.TREND_SHOW:
            period = extract_period_phrase(utterance)
            if period:
                slots["period"] = period
            if state.metric_name:
                slots["context_metric"] = state.metric_name
        if action is SemanticAction.REGRESSION_DETAIL:
            regression_period = _regression_period(utterance)
            if regression_period:
                slots["regression_period"] = regression_period
        return SemanticResolution(
            None if ambiguous else action,
            language,
            confidence=confidence,
            margin=margin,
            ambiguous=ambiguous,
            slots=slots,
            reason="ambiguous" if ambiguous else "semantic",
        )

    def _candidate_actions(
        self, utterance: str, state: DialogueState
    ) -> tuple[SemanticAction, ...]:
        actions = set(_ACTION_DESCRIPTIONS)
        if not state.active_finding_id:
            actions.difference_update(_FINDING_ACTIONS)
        text = normalize_phrase(utterance)
        finding_reference = _has_any(
            text,
            "finding",
            "alert",
            "issue",
            "warning",
            "bulgu",
            "uyari",
            "uyarı",
            "sorun",
        )
        metric_reference = _has_any(
            text, "metric", "indicator", "metri", "gosterge", "gösterge"
        )
        trend_reference = _has_any(
            text,
            "trend",
            "evolve",
            "changed",
            "change over",
            "egilim",
            "eğilim",
            "seyr",
            "degis",
            "değiş",
        )
        meter_reference = _has_any(text, "meter", "sayac", "sayaç")
        regression_reference = _has_any(
            text, "regression", "model", "fit", "regresyon", "uyum"
        )
        findings_inventory = _has_any(
            text,
            "findings",
            "alerts",
            "issues",
            "bulgular",
            "uyarilar",
            "uyarılar",
            "sorunlar",
        )
        inventory_request = _has_any(
            text,
            "list",
            "all",
            "available",
            "inventory",
            "what are",
            "which",
            "listele",
            "tum",
            "tüm",
            "mevcut",
            "kullanilabilir",
            "kullanılabilir",
            "hangi",
            "neler",
        )

        # Bound pronoun-heavy follow-ups to the active domain. Explicit domain
        # words still allow a deliberate finding -> metric/trend switch.
        explicit_switch = any(
            (
                metric_reference,
                trend_reference,
                meter_reference,
                regression_reference,
                findings_inventory,
            )
        )
        if findings_inventory:
            actions.intersection_update({SemanticAction.FINDINGS_LIST})
        elif (
            state.operation == "regression_detail"
            and not explicit_switch
            and not finding_reference
        ):
            actions.intersection_update(
                {SemanticAction.REGRESSION_DETAIL, SemanticAction.REGRESSIONS_LIST}
            )
        elif (
            state.metric_name
            and state.operation in {"metric_detail", "trend"}
            and not finding_reference
        ):
            actions.intersection_update(
                {SemanticAction.METRIC_DETAIL, SemanticAction.TREND_SHOW}
            )
        elif state.active_finding_id and (
            not explicit_switch
            or (
                finding_reference
                and not any(
                    (
                        metric_reference,
                        trend_reference,
                        meter_reference,
                        regression_reference,
                    )
                )
            )
        ):
            actions.intersection_update(_FINDING_ACTIONS)

        if (
            metric_reference
            and not trend_reference
            and not any((meter_reference, regression_reference, findings_inventory))
        ):
            actions.intersection_update(
                {
                    SemanticAction.METRICS_LIST
                    if inventory_request
                    else SemanticAction.METRIC_DETAIL
                }
            )
        elif trend_reference and not any((meter_reference, regression_reference)):
            actions.intersection_update({SemanticAction.TREND_SHOW})
        return tuple(sorted(actions, key=lambda action: action.value))

    def _embed_catalog(
        self, catalog: dict[Any, tuple[str, ...]]
    ) -> dict[Any, list[list[float]]]:
        keys: list[Any] = []
        descriptions: list[str] = []
        for key, values in catalog.items():
            for value in values:
                keys.append(key)
                descriptions.append(f"passage: {value}")
        vectors = self._encoder.embed(descriptions)
        grouped: dict[Any, list[list[float]]] = {key: [] for key in catalog}
        for key, vector in zip(keys, vectors):
            grouped[key].append(vector)
        return grouped


def _dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def _regression_period(utterance: str) -> str:
    text = normalize_phrase(utterance)
    if re.search(r"\b(?:daily|gunluk|günlük)\b", text):
        return "DAILY"
    if re.search(r"\b(?:monthly|aylik|aylık)\b", text):
        return "MONTHLY"
    return ""


def _has_any(text: str, *phrases: str) -> bool:
    return any(normalize_phrase(phrase) in text for phrase in phrases)


def _is_vague_contextual_followup(utterance: str, state: DialogueState) -> bool:
    if not any(
        (
            state.active_finding_id,
            state.metric_name,
            state.entity_id,
            state.period,
            state.operation,
        )
    ):
        return False
    text = normalize_phrase(utterance)
    if len(text.split()) > 6:
        return False
    return not _has_any(
        text,
        "finding",
        "alert",
        "issue",
        "warning",
        "why",
        "cause",
        "trigger",
        "evidence",
        "fact",
        "period",
        "when",
        "date",
        "entity",
        "source",
        "affect",
        "explain",
        "understand",
        "metric",
        "indicator",
        "trend",
        "meter",
        "regression",
        "model",
        "fit",
        "bulgu",
        "uyari",
        "uyarı",
        "sorun",
        "neden",
        "sebep",
        "tetik",
        "kanit",
        "kanıt",
        "dayanak",
        "donem",
        "dönem",
        "zaman",
        "tarih",
        "varlik",
        "varlık",
        "kaynak",
        "etkile",
        "acikla",
        "açıkla",
        "anlam",
        "metri",
        "gosterge",
        "gösterge",
        "egilim",
        "eğilim",
        "sayac",
        "sayaç",
        "regresyon",
        "model",
        "uyum",
    )
