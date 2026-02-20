"""
AVAROS OVOS Skill - Voice-Driven Manufacturing KPI Assistant

This is the main entry point for the OVOS skill that provides voice-based
access to manufacturing KPIs, trends, anomalies, and what-if simulations.

Architecture:
    - Domain models define canonical manufacturing concepts
    - Adapters translate platform-specific APIs to canonical types
    - Use cases orchestrate business logic
    - This skill class handles OVOS voice interactions

Golden Rule:
    AVAROS understands manufacturing concepts.
    Adapters understand platform-specific APIs.
"""

import asyncio
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, List
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler

from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult, ComparisonResult, TrendResult, AnomalyResult, WhatIfResult
from skill.domain.exceptions import AVAROSError
from skill.use_cases.query_dispatcher import QueryDispatcher
from skill.adapters.factory import AdapterFactory
from skill.services.response_builder import ResponseBuilder


class AVAROSSkill(OVOSSkill):
    """
    AVAROS - AI Voice Assistant for Resource-Optimized Sustainable Manufacturing.
    
    This skill provides voice-based access to manufacturing KPIs through
    a platform-agnostic adapter architecture. All voice commands map to
    exactly 5 query types:
    
    1. get_kpi - "What's the OEE for Line-1?"
    2. compare - "Compare energy between Compressor-1 and Compressor-2"
    3. get_trend - "Show scrap rate trend for last week"
    4. check_anomaly - "Any unusual patterns in production?"
    5. simulate_whatif - "What if we reduce temperature by 5 degrees?"
    
    Attributes:
        dispatcher: Routes queries to the appropriate adapter method
        adapter_factory: Creates platform adapters based on configuration
    """
    
    def __init__(self, *args, **kwargs):
        """Initialize skill with default MockAdapter for zero-config deployment."""
        # Set root directory before super().__init__() so OVOS can find locale files
        # Use the directory containing this __init__.py file
        from pathlib import Path
        self._dir = str(Path(__file__).parent)

        # NOTE: OVOS may call initialize() during super().__init__(),
        # so these attributes must exist beforehand.
        self.settings_service = None
        self.adapter_factory: AdapterFactory | None = None
        self.dispatcher: QueryDispatcher | None = None
        self.response_builder: ResponseBuilder | None = None
        self._is_initialized = False
        
        super().__init__(*args, **kwargs)

    @property
    def native_langs(self) -> List[str]:
        """Return only languages that have locale resource files.

        Prevents OVOS from logging 'Unable to find' errors for
        languages we haven't translated yet (e.g. it-IT, es-ES).
        """
        from pathlib import Path
        locale_dir = Path(self.res_dir) / "locale"
        if not locale_dir.is_dir():
            return [self.lang]
        available = [d.name for d in locale_dir.iterdir() if d.is_dir()]
        return available or [self.lang]

    def _run_coro_sync(self, coro):
        """Run async adapter lifecycle hooks from sync OVOS callbacks."""
        try:
            running_loop = asyncio.get_running_loop()
            if running_loop.is_running():
                with ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(asyncio.run, coro).result(timeout=30)
        except RuntimeError:
            pass

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor(max_workers=1) as ex:
                    return ex.submit(asyncio.run, coro).result(timeout=30)
            return loop.run_until_complete(coro)
        except RuntimeError:
            return asyncio.run(coro)

    def initialize(self):
        """
        Called after the skill is fully constructed and registered.
        
        Sets up the adapter factory and query dispatcher. Reads platform
        configuration from SettingsService (DB-backed) if available, otherwise
        uses MockAdapter for zero-config demo deployment (DEC-005).
        """
        if self._is_initialized:
            self.log.debug("AVAROS skill initialize() called again; skipping.")
            return

        # Import SettingsService lazily to avoid circular imports
        from skill.services.settings import SettingsService
        
        # Try to initialize SettingsService with DB backing
        settings_service = None
        try:
            settings_service = SettingsService()
            settings_service.initialize()
            self.log.info("SettingsService initialized successfully")
        except Exception as e:
            self.log.warning(
                "SettingsService initialization failed, using MockAdapter: %s", e
            )
        
        self.settings_service = settings_service
        self.adapter_factory = AdapterFactory(settings_service=self.settings_service)
        adapter = self.adapter_factory.create()
        self.dispatcher = QueryDispatcher(adapter=adapter)
        self.dispatcher._run_async(adapter.initialize())
        self.response_builder = ResponseBuilder(verbosity="normal")
        self._is_initialized = True
        self.log.info("AVAROS skill initialized with adapter: %s", type(adapter).__name__)

    def _safe_dispatch(self, handler_name: str, action: Callable) -> Any:
        """Safely execute a dispatch action with error handling.
        
        Args:
            handler_name: Name of the handler for logging
            action: Callable that performs the query and speaks response
            
        Returns:
            Result from action() or None if error occurred
        """
        if self.dispatcher is None:
            self.speak("AVAROS is still initializing. Please try again.")
            return None
        try:
            return action()
        except AVAROSError as e:
            self.log.warning(
                "Handled domain error in %s: %s (%s)",
                handler_name,
                e,
                getattr(e, "code", "AVAROS_ERROR"),
            )
            self.speak(getattr(e, "user_message", "I couldn't complete that request."))
            return None
        except Exception as e:
            self.log.error("Error in %s: %s", handler_name, e, exc_info=True)
            self.speak("Sorry, I encountered an error. Please try again.")
            return None

    @staticmethod
    def _message_utterance(message) -> str:
        """Return best-effort utterance text from OVOS message."""
        utterance = str(message.data.get("utterance", "")).strip()
        if utterance:
            return utterance
        utterances = message.data.get("utterances") or []
        if utterances:
            return str(utterances[0]).strip()
        return ""

    @staticmethod
    def _normalize_asset_utterance(raw: str) -> str:
        """Normalize common STT variations for asset extraction."""
        text = (raw or "").lower()
        text = re.sub(r"\b(composer|composter|compressor|compulsory|compressor's)\b", "compressor", text)
        number_words = {
            "one": "1",
            "two": "2",
            "three": "3",
            "four": "4",
            "five": "5",
            "six": "6",
            "seven": "7",
            "eight": "8",
            "nine": "9",
            "ten": "10",
        }
        for word, digit in number_words.items():
            text = re.sub(rf"\b{word}\b", digit, text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    @staticmethod
    def _normalize_asset_name(raw: str) -> str:
        """Normalize common spoken asset forms to canonical style."""
        text = AVAROSSkill._normalize_asset_utterance(raw).replace("_", " ")
        text = re.sub(r"\s+", " ", text)
        # "line 1" -> "Line-1", "compressor-2" -> "Compressor-2"
        m = re.match(r"^(line|compressor)\s*-?\s*(\d+)$", text)
        if m:
            return f"{m.group(1).title()}-{m.group(2)}"
        return raw

    def _extract_asset_from_message(self, message, fallback: str = "default") -> str:
        """Extract single asset id from slots or utterance."""
        asset = str(message.data.get("asset", "")).strip()
        if asset:
            return self._normalize_asset_name(asset)
        utterance = self._normalize_asset_utterance(self._message_utterance(message))
        m = re.search(r"\b(line|compressor)\s*-?\s*(\d+)\b", utterance)
        if m:
            return f"{m.group(1).title()}-{m.group(2)}"
        return fallback

    def _extract_compare_assets(self, message) -> tuple[str | None, str | None]:
        """Extract two assets for comparison intent from slots/utterance."""
        asset_a = str(message.data.get("asset_a", "")).strip()
        asset_b = str(message.data.get("asset_b", "")).strip()

        found: list[str] = []
        if asset_a:
            found.append(self._normalize_asset_name(asset_a))
        if asset_b:
            normalized = self._normalize_asset_name(asset_b)
            if normalized not in found:
                found.append(normalized)

        utterance = self._normalize_asset_utterance(self._message_utterance(message))
        parsed_mentions: list[tuple[str, str]] = []
        for match in re.finditer(r"\b(line|compressor)\s*-?\s*(\d+)?\b", utterance):
            asset_type = match.group(1).title()
            asset_num = (match.group(2) or "").strip()
            parsed_mentions.append((asset_type, asset_num))
            if not asset_num:
                continue
            candidate = f"{asset_type}-{asset_num}"
            if candidate not in found:
                found.append(candidate)
            if len(found) >= 2:
                break

        if len(found) == 1:
            # Heuristic for STT outputs like "compressor 1 and compulsory":
            # second mention may lose its numeric suffix.
            numbered = [item for item in parsed_mentions if item[1]]
            unnumbered = [item for item in parsed_mentions if not item[1]]
            if numbered and unnumbered:
                first_type, first_num = numbered[0]
                second_type, _ = unnumbered[0]
                if first_type == second_type:
                    inferred = str(int(first_num) + 1)
                    candidate = f"{second_type}-{inferred}"
                    if candidate not in found:
                        found.append(candidate)

        if len(found) >= 2:
            return found[0], found[1]
        return None, None

    # =========================================================================
    # Conversational Helpers
    # =========================================================================

    @intent_handler("greeting.intent")
    def handle_greeting(self, message):
        """Handle greetings such as 'hello' or 'hey avaros'."""
        self.speak_dialog("greeting.response")

    @intent_handler("help.intent")
    def handle_help(self, message):
        """Handle generic help requests."""
        self.speak_dialog("help.response")

    def converse(self, message) -> bool:
        """Provide a short fallback for brief domain-out utterances."""
        utterance = (message.data.get("utterances") or [""])[0].lower().strip()
        domain_keywords = [
            "energy",
            "scrap",
            "oee",
            "anomaly",
            "trend",
            "temperature",
            "compare",
            "production",
            "kpi",
        ]
        if utterance and len(utterance.split()) <= 2 and not any(
            keyword in utterance for keyword in domain_keywords
        ):
            self.speak(
                "I'm a manufacturing assistant. Try: 'show energy trend today' or 'check production anomaly'."
            )
            return True
        return False

    # =========================================================================
    # KPI Query Handlers
    # =========================================================================
    
    @intent_handler("kpi.energy.per_unit.intent")
    def handle_kpi_energy_per_unit(self, message):
        """Handle: 'What's the energy per unit for {asset}?'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            period_value = message.data.get("period", "today")
            # Padatious may capture temporal words (e.g. "today") as {asset}
            # for some phrasings; treat that as period and use default asset.
            if (
                isinstance(asset_id, str)
                and not message.data.get("period")
                and asset_id.strip().lower() in {
                    "today",
                    "yesterday",
                    "this week",
                    "last week",
                    "this month",
                    "last month",
                    "this year",
                    "last year",
                }
            ):
                period_value = asset_id
                asset_id = "default"
            period = self._parse_period(period_value)
            
            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id=asset_id,
                period=period
            )
            
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_kpi_energy_per_unit", _execute)

    @intent_handler("kpi.oee.intent")
    def handle_kpi_oee(self, message):
        """Handle: 'What's the OEE for {asset}?'"""
        def _execute():
            asset_id = self._extract_asset_from_message(message, fallback="default")
            period = self._parse_period(message.data.get("period", "today"))

            try:
                result: KPIResult = self.dispatcher.get_kpi(
                    metric=CanonicalMetric.OEE,
                    asset_id=asset_id,
                    period=period
                )
                response = self.response_builder.format_kpi_result(result)
                self.speak(response)
            except AVAROSError as exc:
                msg = str(getattr(exc, "user_message", "") or "").lower()
                code = str(getattr(exc, "code", "") or "")
                if "not available" in msg or code in {"RENERYO_ENDPOINT_NOT_FOUND", "METRIC_NOT_SUPPORTED"}:
                    fallback_result: KPIResult = self.dispatcher.get_kpi(
                        metric=CanonicalMetric.ENERGY_PER_UNIT,
                        asset_id=asset_id,
                        period=period
                    )
                    fallback_response = self.response_builder.format_kpi_result(fallback_result)
                    self.speak(
                        "OEE is not available in this RENERYO environment yet. "
                        + fallback_response
                    )
                    return
                raise
        
        self._safe_dispatch("handle_kpi_oee", _execute)

    @intent_handler("kpi.scrap_rate.intent")
    def handle_kpi_scrap_rate(self, message):
        """Handle: 'What's the scrap rate?'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            period = self._parse_period(message.data.get("period", "today"))
            
            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SCRAP_RATE,
                asset_id=asset_id,
                period=period
            )
            
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_kpi_scrap_rate", _execute)

    # =========================================================================
    # Compare Query Handlers
    # =========================================================================
    
    @intent_handler("compare.energy.intent")
    def handle_compare_energy(self, message):
        """Handle: 'Compare energy between {asset_a} and {asset_b}'"""
        def _execute():
            asset_a, asset_b = self._extract_compare_assets(message)
            if not asset_a or not asset_b:
                self.speak(
                    "Please name two assets. For example: compare energy between Compressor-1 and Compressor-2."
                )
                return
            period = self._parse_period(message.data.get("period", "today"))

            try:
                result: ComparisonResult = self.dispatcher.compare(
                    metric=CanonicalMetric.ENERGY_PER_UNIT,
                    asset_ids=[asset_a, asset_b],
                    period=period
                )
                response = self.response_builder.format_comparison_result(result)
                self.speak(response)
            except Exception:
                self.log.warning(
                    "Compare failed for assets: %s, %s",
                    asset_a,
                    asset_b,
                    exc_info=True,
                )
                self.speak(
                    "I couldn't compare those assets right now. "
                    "Please try exact names, for example: Compressor-1 and Compressor-2."
                )
        
        self._safe_dispatch("handle_compare_energy", _execute)

    # =========================================================================
    # Trend Query Handlers
    # =========================================================================
    
    @intent_handler("trend.scrap.intent")
    def handle_trend_scrap(self, message):
        """Handle: 'Show scrap rate trend for {period}'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            period = self._parse_period(message.data.get("period", "last week"))
            granularity = message.data.get("granularity", "daily")
            
            result: TrendResult = self.dispatcher.get_trend(
                metric=CanonicalMetric.SCRAP_RATE,
                asset_id=asset_id,
                period=period,
                granularity=granularity
            )
            
            response = self.response_builder.format_trend_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_trend_scrap", _execute)

    @intent_handler("trend.energy.intent")
    def handle_trend_energy(self, message):
        """Handle: 'Show energy trend for {period}'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            period = self._parse_period(message.data.get("period", "last week"))
            granularity = message.data.get("granularity", "daily")
            
            result: TrendResult = self.dispatcher.get_trend(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id=asset_id,
                period=period,
                granularity=granularity
            )
            
            response = self.response_builder.format_trend_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_trend_energy", _execute)

    # =========================================================================
    # Anomaly Query Handlers
    # =========================================================================
    
    @intent_handler("anomaly.production.check.intent")
    def handle_anomaly_check(self, message):
        """Handle: 'Any unusual patterns in production?'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            
            result: AnomalyResult = self.dispatcher.check_anomaly(
                metric=CanonicalMetric.OEE,
                asset_id=asset_id
            )
            
            response = self.response_builder.format_anomaly_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_anomaly_check", _execute)

    # =========================================================================
    # What-If Query Handlers
    # =========================================================================
    
    @intent_handler("whatif.temperature.intent")
    def handle_whatif_temperature(self, message):
        """Handle: 'What if we increase/decrease temperature by {amount} degrees?'"""
        def _execute():
            from skill.domain.models import WhatIfScenario, ScenarioParameter

            raw_amount = str(message.data.get("amount", "5")).strip()
            try:
                amount = abs(float(raw_amount))
            except (TypeError, ValueError):
                amount = 5.0

            direction = str(message.data.get("direction", "")).strip().lower()
            utterance = str(message.data.get("utterance", "")).strip().lower()
            if not direction:
                if any(token in utterance for token in ("increase", "raise", "up")):
                    direction = "increase"
                else:
                    direction = "decrease"

            is_increase = direction in {
                "increase", "increases", "increased",
                "raise", "raises", "raised", "up",
            }
            proposed_value = 25.0 + amount if is_increase else 25.0 - amount

            asset_id = message.data.get("asset", "default")
            
            scenario = WhatIfScenario(
                name="temperature_change",
                asset_id=asset_id,
                parameters=[
                    ScenarioParameter(
                        name="temperature",
                        baseline_value=25.0,
                        proposed_value=proposed_value,
                        unit="°C"
                    )
                ],
                target_metric=CanonicalMetric.ENERGY_PER_UNIT
            )
            
            result: WhatIfResult = self.dispatcher.simulate_whatif(scenario)
            
            response = self.response_builder.format_whatif_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_whatif_temperature", _execute)

    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _parse_period(self, period_str: str) -> TimePeriod:
        """Parse natural language period into TimePeriod value object."""
        return TimePeriod.from_natural_language(period_str)

    def stop(self):
        """Optional cleanup when skill is stopped."""
        dispatcher = getattr(self, "dispatcher", None)
        if dispatcher is not None:
            dispatcher.shutdown()
            self._is_initialized = False


def create_skill():
    """OVOS entry point - creates and returns the skill instance."""
    return AVAROSSkill()
