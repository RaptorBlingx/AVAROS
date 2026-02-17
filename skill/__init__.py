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

from typing import Any, Callable, List

from ovos_workshop.decorators import intent_handler
from ovos_workshop.skills import OVOSSkill

from skill.adapters.factory import AdapterFactory
from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import (
    AnomalyResult,
    ComparisonResult,
    KPIResult,
    TrendResult,
    WhatIfResult,
)
from skill.services.response_builder import ResponseBuilder
from skill.use_cases.query_dispatcher import QueryDispatcher


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
        
        super().__init__(*args, **kwargs)
        
        self.settings_service = None
        self.adapter_factory: AdapterFactory | None = None
        self.dispatcher: QueryDispatcher | None = None
        self.response_builder: ResponseBuilder | None = None
        self._loaded_profile: str = "mock"

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

    def initialize(self):
        """
        Called after the skill is fully constructed and registered.
        
        Sets up the adapter factory and query dispatcher. Reads platform
        configuration from SettingsService (DB-backed) if available, otherwise
        uses MockAdapter for zero-config demo deployment (DEC-005).
        """
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
        self.response_builder = ResponseBuilder(verbosity="normal")

        # Track active profile for lazy-reload (DEC-029)
        self._loaded_profile = self._resolve_active_profile()

        # Listen for profile activation events from Web UI (DEC-029)
        self.bus.on("avaros.profile.activated", self._handle_profile_switch)
        self.log.info(
            "AVAROS skill initialized with adapter: %s (profile='%s')",
            type(adapter).__name__,
            self._loaded_profile,
        )

    # =================================================================
    # Profile Reload (DEC-029)
    # =================================================================

    def _resolve_active_profile(self) -> str:
        """Return the active profile name from SettingsService.

        Returns:
            Profile name, or ``"mock"`` when unavailable.
        """
        if self.settings_service is None:
            return "mock"
        try:
            return self.settings_service.get_active_profile_name()
        except Exception:
            return "mock"

    def _handle_profile_switch(self, message) -> None:
        """Reload adapter when profile is switched via Web UI.

        Triggered by ``avaros.profile.activated`` message bus event.
        Gracefully handles reload failures by falling back to
        MockAdapter (DEC-005).

        Args:
            message: OVOS message with ``data.profile`` string.
        """
        profile_name = message.data.get("profile", "")
        self.log.info(
            "Profile switch event received: '%s'", profile_name,
        )
        try:
            self._reload_adapter(profile_name)
        except Exception as exc:
            self.log.error(
                "Profile switch reload failed: %s — falling back to mock",
                exc,
            )
            self._force_mock_fallback()

    def _reload_adapter(self, profile_name: str) -> None:
        """Reload adapter factory and rebuild QueryDispatcher.

        Args:
            profile_name: Profile that triggered the reload.
        """
        if self.adapter_factory is None:
            self.log.warning("No adapter factory — cannot reload")
            return

        import asyncio

        loop = asyncio.new_event_loop()
        try:
            new_adapter = loop.run_until_complete(
                self.adapter_factory.reload(profile_name),
            )
        finally:
            loop.close()

        self.dispatcher = QueryDispatcher(adapter=new_adapter)
        self._loaded_profile = profile_name
        self.log.info(
            "Adapter reloaded: %s (profile='%s')",
            type(new_adapter).__name__,
            profile_name,
        )

    def _force_mock_fallback(self) -> None:
        """Force MockAdapter as a safety fallback (DEC-005)."""
        from skill.adapters.mock import MockAdapter

        mock = MockAdapter()
        self.dispatcher = QueryDispatcher(adapter=mock)
        self._loaded_profile = "mock"
        self.log.info("Forced MockAdapter fallback")

    def _check_profile_mismatch(self) -> None:
        """Reload adapter if active profile differs from loaded one.

        Defense-in-depth: ensures the skill eventually catches up
        even if the message bus notification was missed.
        """
        if self.settings_service is None:
            return
        try:
            current = self.settings_service.get_active_profile_name()
            if current != self._loaded_profile:
                self.log.info(
                    "Profile mismatch: loaded='%s', active='%s'. Reloading.",
                    self._loaded_profile,
                    current,
                )
                self._reload_adapter(current)
        except Exception as exc:
            self.log.warning("Profile mismatch check failed: %s", exc)

    # =================================================================
    # Dispatch
    # =================================================================

    def _safe_dispatch(self, handler_name: str, action: Callable) -> Any:
        """Safely execute a dispatch action with error handling.

        Args:
            handler_name: Name of the handler for logging.
            action: Callable that performs the query and speaks response.

        Returns:
            Result from action() or None if error occurred.
        """
        if self.dispatcher is None:
            self.speak("AVAROS is still initializing. Please try again.")
            return None

        # DEC-029: lazy profile reload if message bus event was missed
        self._check_profile_mismatch()

        try:
            return action()
        except Exception as e:
            self.log.error("Error in %s: %s", handler_name, e, exc_info=True)
            self.speak("Sorry, I encountered an error. Please try again.")
            return None

    # =========================================================================
    # KPI Query Handlers
    # =========================================================================
    
    @intent_handler("kpi.energy.per_unit.intent")
    def handle_kpi_energy_per_unit(self, message):
        """Handle: 'What's the energy per unit for {asset}?'"""
        def _execute():
            asset_id = message.data.get("asset", "default")
            period = self._parse_period(message.data.get("period", "today"))
            
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
            asset_id = message.data.get("asset", "default")
            period = self._parse_period(message.data.get("period", "today"))
            
            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.OEE,
                asset_id=asset_id,
                period=period
            )
            
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
        
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
            asset_a = message.data.get("asset_a", "Asset-1")
            asset_b = message.data.get("asset_b", "Asset-2")
            period = self._parse_period(message.data.get("period", "today"))
            
            result: ComparisonResult = self.dispatcher.compare(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_ids=[asset_a, asset_b],
                period=period
            )
            
            response = self.response_builder.format_comparison_result(result)
            self.speak(response)
        
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
        """Handle: 'What if we reduce temperature by {amount} degrees?'"""
        def _execute():
            from skill.domain.models import WhatIfScenario, ScenarioParameter
            
            amount = float(message.data.get("amount", "5"))
            asset_id = message.data.get("asset", "default")
            
            scenario = WhatIfScenario(
                name="temperature_change",
                asset_id=asset_id,
                parameters=[
                    ScenarioParameter(
                        name="temperature",
                        baseline_value=25.0,
                        proposed_value=25.0 - amount,
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
        pass


def create_skill():
    """OVOS entry point - creates and returns the skill instance."""
    return AVAROSSkill()
