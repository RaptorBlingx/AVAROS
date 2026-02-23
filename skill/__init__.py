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

import re
from typing import Any, Callable, List

from ovos_workshop.decorators import fallback_handler, intent_handler
from ovos_workshop.skills import FallbackSkill

from skill.adapters.factory import AdapterFactory
from skill.domain.exceptions import AVAROSError
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


class AVAROSSkill(FallbackSkill):
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

        # OVOS may call initialize() during super().__init__(), so define
        # runtime attributes before calling into base class startup.
        self.settings_service = None
        self.adapter_factory: AdapterFactory | None = None
        self.dispatcher: QueryDispatcher | None = None
        self.response_builder: ResponseBuilder | None = None
        self._loaded_profile: str = "mock"
        self._loaded_platform: str = "mock"
        self._is_initialized: bool = False

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

    def initialize(self):
        """
        Called after the skill is fully constructed and registered.
        
        Sets up the adapter factory and query dispatcher. Reads platform
        configuration from SettingsService (DB-backed) if available, otherwise
        uses MockAdapter for zero-config demo deployment (DEC-005).
        """
        if self._is_initialized:
            self.log.info("AVAROS skill already initialized; skipping duplicate initialize()")
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
        try:
            # Initialize adapter in the dispatcher's runtime loop to avoid
            # cross-loop aiohttp session ownership and leaked sessions.
            self.dispatcher._run_async(adapter.initialize())
        except Exception as exc:
            self.log.warning(
                "Adapter initialize failed at startup: %s", exc,
            )
        self.response_builder = ResponseBuilder(verbosity="normal")

        # Track active profile for lazy-reload (DEC-029)
        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = adapter.platform_name.lower()

        # Listen for profile activation events from Web UI (DEC-029)
        self.bus.on("avaros.profile.activated", self._handle_profile_switch)
        # Recover missed KPI utterances when intent matching fails
        self.bus.on("intent_failure", self._handle_intent_failure)
        self.log.info(
            "AVAROS skill initialized with adapter: %s (profile='%s')",
            type(adapter).__name__,
            self._loaded_profile,
        )
        self._is_initialized = True

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
            self._ensure_runtime_services()
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
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(verbosity="normal")
        self._loaded_profile = self._resolve_active_profile()
        self._loaded_platform = new_adapter.platform_name.lower()
        self.log.info(
            "Adapter reloaded: %s (profile='%s', platform='%s')",
            type(new_adapter).__name__,
            self._loaded_profile,
            self._loaded_platform,
        )

    def _force_mock_fallback(self) -> None:
        """Force MockAdapter as a safety fallback (DEC-005)."""
        from skill.adapters.mock import MockAdapter

        mock = MockAdapter()
        self.dispatcher = QueryDispatcher(adapter=mock)
        if self.response_builder is None:
            self.response_builder = ResponseBuilder(verbosity="normal")
        self._loaded_profile = "mock"
        self._loaded_platform = "mock"
        self.log.info("Forced MockAdapter fallback")

    def _expected_platform_for_profile(self, profile_name: str) -> str:
        """Resolve expected platform type for a given profile."""
        if self.settings_service is None:
            return "mock"
        try:
            config = self.settings_service.get_profile(profile_name)
            if config is None:
                return "mock"
            platform = (config.platform_type or "mock").strip().lower()
            return platform or "mock"
        except Exception:
            return "mock"

    def _ensure_runtime_services(self) -> None:
        """Recreate SettingsService / AdapterFactory if missing at runtime."""
        if self.settings_service is None:
            try:
                from skill.services.settings import SettingsService

                settings_service = SettingsService()
                settings_service.initialize()
                self.settings_service = settings_service
                self.log.info("Recovered SettingsService at runtime")
            except Exception as exc:
                self.log.warning(
                    "Runtime SettingsService recovery failed: %s", exc,
                )

        if self.adapter_factory is None and self.settings_service is not None:
            self.adapter_factory = AdapterFactory(
                settings_service=self.settings_service,
            )
            self.log.info("Recovered AdapterFactory at runtime")

    def _check_profile_mismatch(self) -> None:
        """Reload adapter if active profile differs from loaded one.

        Defense-in-depth: ensures the skill eventually catches up
        even if the message bus notification was missed.
        """
        if self.settings_service is None:
            return
        try:
            current = self.settings_service.get_active_profile_name()
            expected_platform = self._expected_platform_for_profile(current)
            if (
                current != self._loaded_profile
                or expected_platform != self._loaded_platform
            ):
                self.log.info(
                    (
                        "Profile/platform mismatch: loaded_profile='%s', "
                        "active_profile='%s', loaded_platform='%s', "
                        "expected_platform='%s'. Reloading."
                    ),
                    self._loaded_profile,
                    current,
                    self._loaded_platform,
                    expected_platform,
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
        self._ensure_runtime_services()

        if self.dispatcher is None:
            self.log.warning(
                "Dispatcher missing in %s; attempting recovery",
                handler_name,
            )
            try:
                if self.settings_service is not None:
                    profile = self.settings_service.get_active_profile_name()
                    self._reload_adapter(profile)
                else:
                    self._force_mock_fallback()
            except Exception as exc:
                self.log.warning("Dispatcher recovery failed: %s", exc)

            if self.dispatcher is None:
                self.speak("AVAROS is still initializing. Please try again.")
                return None

        if self.response_builder is None:
            self.log.warning(
                "Response builder missing in %s; recovering",
                handler_name,
            )
            self.response_builder = ResponseBuilder(verbosity="normal")

        # DEC-029: lazy profile reload if message bus event was missed
        self._check_profile_mismatch()

        try:
            return action()
        except AVAROSError as e:
            self.log.error("Error in %s: %s", handler_name, e, exc_info=True)
            self.speak(e.user_message)
            return None
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
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))
            
            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.ENERGY_PER_UNIT,
                asset_id=asset_id,
                period=period
            )
            
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_kpi_energy_per_unit", _execute)

    @intent_handler("kpi.energy.total.intent")
    def handle_kpi_energy_total(self, message):
        """Handle: 'What's the total energy for {asset}?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.ENERGY_TOTAL,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_energy_total", _execute)

    @intent_handler("greeting.intent")
    def handle_greeting(self, message):
        """Handle greetings such as 'hello' or 'hey avaros'."""
        self.speak_dialog("greeting.response")

    @intent_handler("help.intent")
    def handle_help(self, message):
        """Handle generic help requests."""
        self.speak_dialog("help.response")

    @intent_handler("kpi.oee.intent")
    def handle_kpi_oee(self, message):
        """Handle: 'What's the OEE for {asset}?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
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
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))
            
            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SCRAP_RATE,
                asset_id=asset_id,
                period=period
            )
            
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
        
        self._safe_dispatch("handle_kpi_scrap_rate", _execute)

    @intent_handler("kpi.peak_demand.intent")
    def handle_kpi_peak_demand(self, message):
        """Handle: 'What's the peak demand?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.PEAK_DEMAND,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_peak_demand", _execute)

    @intent_handler("kpi.peak_tariff_exposure.intent")
    def handle_kpi_peak_tariff_exposure(self, message):
        """Handle: 'What's the peak tariff exposure?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.PEAK_TARIFF_EXPOSURE,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_peak_tariff_exposure", _execute)

    @intent_handler("kpi.rework_rate.intent")
    def handle_kpi_rework_rate(self, message):
        """Handle: 'What's the rework rate?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.REWORK_RATE,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_rework_rate", _execute)

    @intent_handler("kpi.material_efficiency.intent")
    def handle_kpi_material_efficiency(self, message):
        """Handle: 'What's the material efficiency?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.MATERIAL_EFFICIENCY,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_material_efficiency", _execute)

    @intent_handler("kpi.recycled_content.intent")
    def handle_kpi_recycled_content(self, message):
        """Handle: 'What's the recycled content?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.RECYCLED_CONTENT,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_recycled_content", _execute)

    @intent_handler("kpi.supplier_lead_time.intent")
    def handle_kpi_supplier_lead_time(self, message):
        """Handle: 'What's the supplier lead time?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SUPPLIER_LEAD_TIME,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_supplier_lead_time", _execute)

    @intent_handler("kpi.supplier_defect_rate.intent")
    def handle_kpi_supplier_defect_rate(self, message):
        """Handle: 'What's the supplier defect rate?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SUPPLIER_DEFECT_RATE,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_supplier_defect_rate", _execute)

    @intent_handler("kpi.supplier_on_time.intent")
    def handle_kpi_supplier_on_time(self, message):
        """Handle: 'What's the supplier on-time rate?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SUPPLIER_ON_TIME,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_supplier_on_time", _execute)

    @intent_handler("kpi.supplier_co2_per_kg.intent")
    def handle_kpi_supplier_co2_per_kg(self, message):
        """Handle: 'What's supplier CO2 per kg?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.SUPPLIER_CO2_PER_KG,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_supplier_co2_per_kg", _execute)

    @intent_handler("kpi.throughput.intent")
    def handle_kpi_throughput(self, message):
        """Handle: 'What's the throughput?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.THROUGHPUT,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_throughput", _execute)

    @intent_handler("kpi.cycle_time.intent")
    def handle_kpi_cycle_time(self, message):
        """Handle: 'What's the cycle time?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.CYCLE_TIME,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_cycle_time", _execute)

    @intent_handler("kpi.changeover_time.intent")
    def handle_kpi_changeover_time(self, message):
        """Handle: 'What's the changeover time?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.CHANGEOVER_TIME,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_changeover_time", _execute)

    @intent_handler("kpi.co2.per_unit.intent")
    def handle_kpi_co2_per_unit(self, message):
        """Handle: 'What's CO2 per unit?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.CO2_PER_UNIT,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_co2_per_unit", _execute)

    @intent_handler("kpi.co2.total.intent")
    def handle_kpi_co2_total(self, message):
        """Handle: 'What's total CO2?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.CO2_TOTAL,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_co2_total", _execute)

    @intent_handler("kpi.co2.per_batch.intent")
    def handle_kpi_co2_per_batch(self, message):
        """Handle: 'What's CO2 per batch?'"""
        def _execute():
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "today"))

            result: KPIResult = self.dispatcher.get_kpi(
                metric=CanonicalMetric.CO2_PER_BATCH,
                asset_id=asset_id,
                period=period,
            )

            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("handle_kpi_co2_per_batch", _execute)

    # =========================================================================
    # Compare Query Handlers
    # =========================================================================
    
    @intent_handler("compare.energy.intent")
    def handle_compare_energy(self, message):
        """Handle: 'Compare energy between {asset_a} and {asset_b}'"""
        def _execute():
            asset_a, asset_b = self._resolve_compare_assets(message)
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
            asset_id = self._resolve_asset_id(message)
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
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(message.data.get("period", "last week"))
            granularity = message.data.get("granularity", "daily")
            if period.duration_days < 2 and granularity == "daily":
                granularity = "hourly"
            
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
            asset_id = self._resolve_asset_id(message)
            
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
            
            amount = self._resolve_temperature_amount(message)
            asset_id = self._resolve_asset_id(message)
            
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
    # Generic Control & Status Handlers
    # =========================================================================

    @intent_handler("control.device.turn_on.intent")
    def handle_control_turn_on(self, message):
        """Handle generic turn-on command (platform-agnostic mock default)."""

        def _execute():
            if not self._require_intent_binding("control.device.turn_on"):
                return
            target = self._resolve_asset_id(message, default="system")
            self._set_power_state("on")
            self.speak(f"Power state is now on for {target}.")

        self._safe_dispatch("handle_control_turn_on", _execute)

    @intent_handler("control.device.turn_off.intent")
    def handle_control_turn_off(self, message):
        """Handle generic turn-off command (platform-agnostic mock default)."""

        def _execute():
            if not self._require_intent_binding("control.device.turn_off"):
                return
            target = self._resolve_asset_id(message, default="system")
            self._set_power_state("off")
            self.speak(f"Power state is now off for {target}.")

        self._safe_dispatch("handle_control_turn_off", _execute)

    @intent_handler("status.system.show.intent")
    def handle_status_system_show(self, message):
        """Handle generic system status request."""

        def _execute():
            if not self._require_intent_binding("status.system.show"):
                return
            active_profile = self._resolve_active_profile()
            power_state = self._get_power_state()
            platform = "mock"
            if self.settings_service is not None:
                config = self.settings_service.get_profile(active_profile)
                if config is not None:
                    platform = config.platform_type
            adapter_name = (
                type(self.dispatcher._adapter).__name__
                if self.dispatcher is not None
                else "UnknownAdapter"
            )
            health = "online" if power_state == "on" else "offline"
            self.speak(
                f"System is {health}. Active profile is {active_profile} on platform {platform}, and adapter is {adapter_name}."
            )

        self._safe_dispatch("handle_status_system_show", _execute)

    @intent_handler("status.profile.show.intent")
    def handle_status_profile_show(self, message):
        """Handle profile/config status request."""

        def _execute():
            if not self._require_intent_binding("status.profile.show"):
                return
            profile = self._resolve_active_profile()
            platform = "mock"
            if self.settings_service is not None:
                config = self.settings_service.get_profile(profile)
                if config is not None:
                    platform = config.platform_type
            self.speak(
                f"Current profile is {profile} on platform {platform}."
            )

        self._safe_dispatch("handle_status_profile_show", _execute)

    @intent_handler("help.capabilities.list.intent")
    def handle_help_capabilities_list(self, message):
        """Handle capability/help request for generic + KPI intents."""

        def _execute():
            if not self._require_intent_binding("help.capabilities.list"):
                return
            self.speak(
                "I can report KPIs, compare and trend metrics, check anomalies, run what if simulations, "
                "and handle generic commands like turn on, turn off, and show status."
            )

        self._safe_dispatch("handle_help_capabilities_list", _execute)

    @fallback_handler(95)
    def handle_metric_query_fallback(self, message):
        """Fallback: resolve metric KPI queries missed by strict intent parsing."""
        utterance = self._extract_utterance_text(message).lower()
        if self._is_anomaly_query(utterance):
            def _execute_anomaly():
                asset_id = self._resolve_asset_id(message)
                result: AnomalyResult = self.dispatcher.check_anomaly(
                    metric=CanonicalMetric.OEE,
                    asset_id=asset_id,
                )
                response = self.response_builder.format_anomaly_result(result)
                self.speak(response)
                return True

            handled = self._safe_dispatch(
                "handle_metric_query_fallback_anomaly",
                _execute_anomaly,
            )
            return bool(handled)

        metric = self._resolve_metric_from_utterance(utterance)
        if metric is None:
            return False

        def _execute():
            data = getattr(message, "data", {}) or {}
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(data.get("period", "today"))
            result: KPIResult = self.dispatcher.get_kpi(
                metric=metric,
                asset_id=asset_id,
                period=period,
            )
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)
            return True

        handled = self._safe_dispatch("handle_metric_query_fallback", _execute)
        return bool(handled)

    def _handle_intent_failure(self, message) -> None:
        """Recover KPI queries from global intent-failure events."""
        utterance = self._extract_utterance_text(message).lower()
        if self._is_anomaly_query(utterance):
            def _execute_anomaly():
                asset_id = self._resolve_asset_id(message)
                result: AnomalyResult = self.dispatcher.check_anomaly(
                    metric=CanonicalMetric.OEE,
                    asset_id=asset_id,
                )
                response = self.response_builder.format_anomaly_result(result)
                self.speak(response)

            self._safe_dispatch(
                "_handle_intent_failure_anomaly",
                _execute_anomaly,
            )
            return

        metric = self._resolve_metric_from_utterance(utterance)
        if metric is None:
            return

        def _execute():
            data = getattr(message, "data", {}) or {}
            asset_id = self._resolve_asset_id(message)
            period = self._parse_period(data.get("period", "today"))
            result: KPIResult = self.dispatcher.get_kpi(
                metric=metric,
                asset_id=asset_id,
                period=period,
            )
            response = self.response_builder.format_kpi_result(result)
            self.speak(response)

        self._safe_dispatch("_handle_intent_failure", _execute)

    def can_answer(self, message) -> bool:
        """Tell OVOS fallback service when this skill can answer utterance."""
        data = getattr(message, "data", {}) or {}
        utterances = data.get("utterances")
        if isinstance(utterances, list) and utterances:
            text = str(utterances[0]).lower()
        else:
            text = self._extract_utterance_text(message).lower()
        if not text.strip():
            return True
        return (
            self._resolve_metric_from_utterance(text) is not None
            or self._is_anomaly_query(text)
        )

    def _is_anomaly_query(self, utterance: str) -> bool:
        """Return True when utterance asks for anomaly/unusual pattern checks."""
        if not utterance:
            return False
        normalized = re.sub(r"[^a-z0-9\s]", " ", utterance.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()
        anomaly_patterns = (
            "check anomalies",
            "check anomaly",
            "check for anomalies",
            "anomaly check",
            "any anomalies",
            "unusual patterns",
            "anything unusual",
            "spikes or issues",
        )
        return any(pattern in normalized for pattern in anomaly_patterns)

    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _parse_period(self, period_str: str) -> TimePeriod:
        """Parse natural language period into TimePeriod value object."""
        return TimePeriod.from_natural_language(period_str)

    def _resolve_metric_from_utterance(
        self,
        utterance: str,
    ) -> CanonicalMetric | None:
        """Resolve a canonical metric from free-form KPI utterance text."""
        if not utterance:
            return None
        normalized = re.sub(r"[^a-z0-9\s]", " ", utterance.lower())
        normalized = re.sub(r"\s+", " ", normalized).strip()

        co2_like = bool(
            re.search(r"\bco\s*2\b", normalized)
            or re.search(r"\bco2\b", normalized)
            or re.search(r"\bco\s*two\b", normalized)
            or "carbon dioxide" in normalized
            or "carbon emissions" in normalized
        )
        total_like = bool(
            "total" in normalized
            or re.search(r"\btot\w*\b", normalized)
            or "emissions" in normalized
        )
        if co2_like and total_like:
            return CanonicalMetric.CO2_TOTAL

        phrase_map: list[tuple[CanonicalMetric, tuple[str, ...]]] = [
            (CanonicalMetric.ENERGY_PER_UNIT, (
                "energy per unit", "power per unit", "electricity per unit",
                "energy consumption per unit", "specific energy", "specific power",
            )),
            (CanonicalMetric.ENERGY_TOTAL, (
                "total energy", "energy total", "total power", "total electricity",
                "energy consumption", "power consumption",
            )),
            (CanonicalMetric.PEAK_DEMAND, (
                "peak demand", "maximum demand", "max demand", "peak power demand",
            )),
            (CanonicalMetric.PEAK_TARIFF_EXPOSURE, (
                "peak tariff exposure", "tariff exposure",
            )),
            (CanonicalMetric.REWORK_RATE, ("rework rate", "rework")),
            (CanonicalMetric.MATERIAL_EFFICIENCY, ("material efficiency",)),
            (CanonicalMetric.RECYCLED_CONTENT, ("recycled content",)),
            (CanonicalMetric.SUPPLIER_LEAD_TIME, ("supplier lead time", "lead time")),
            (CanonicalMetric.SUPPLIER_DEFECT_RATE, ("supplier defect rate", "defect rate")),
            (CanonicalMetric.SUPPLIER_ON_TIME, ("supplier on time", "on time delivery")),
            (CanonicalMetric.SUPPLIER_CO2_PER_KG, (
                "supplier co2 per kg", "supplier co 2 per kg", "supplier co two per kg",
                "supplier carbon dioxide per kilogram", "supplier emissions per kilogram",
            )),
            (CanonicalMetric.THROUGHPUT, ("throughput",)),
            (CanonicalMetric.CYCLE_TIME, ("cycle time",)),
            (CanonicalMetric.CHANGEOVER_TIME, ("changeover time", "change over time")),
            (CanonicalMetric.CO2_PER_UNIT, (
                "co2 per unit", "co 2 per unit", "co two per unit",
                "carbon dioxide per unit", "emissions per unit",
            )),
            (CanonicalMetric.CO2_TOTAL, (
                "co2 total", "co 2 total", "co two total", "total co2",
                "total co 2", "total co two", "total carbon", "total carbon emissions",
                "total emissions",
            )),
            (CanonicalMetric.CO2_PER_BATCH, (
                "co2 per batch", "co 2 per batch", "co two per batch",
                "carbon dioxide per batch", "emissions per batch",
            )),
        ]
        for metric, phrases in phrase_map:
            if any(phrase in normalized for phrase in phrases):
                return metric
        return None

    def _is_non_mock_profile(self) -> bool:
        """Return True when active profile is not built-in mock."""
        return self._resolve_active_profile() != "mock"

    def _get_intent_binding(self, intent_name: str) -> dict | None:
        """Return configured binding for a non-metric intent."""
        if self.settings_service is None:
            return None
        try:
            return self.settings_service.get_intent_binding(intent_name)
        except Exception as exc:
            self.log.warning(
                "Intent binding read failed for %s: %s",
                intent_name,
                exc,
            )
            return None

    def _require_intent_binding(self, intent_name: str) -> bool:
        """Require binding on non-mock profiles before executing handler."""
        if not self._is_non_mock_profile():
            return True
        binding = self._get_intent_binding(intent_name)
        if binding is not None:
            return True
        self.speak(
            "This command is not configured for the active profile yet. "
            "Add an intent binding in Settings first."
        )
        return False

    def _power_state_key(self, profile: str) -> str:
        """Build profile-scoped runtime power-state key."""
        return f"runtime:power_state:{profile}"

    def _get_power_state(self) -> str:
        """Return profile-scoped runtime power state (on/off)."""
        profile = self._resolve_active_profile()
        if self.settings_service is None:
            return "on"
        value = self.settings_service.get_setting(
            self._power_state_key(profile),
            default="on",
        )
        state = str(value or "on").strip().lower()
        return "off" if state == "off" else "on"

    def _set_power_state(self, state: str) -> None:
        """Persist profile-scoped runtime power state."""
        profile = self._resolve_active_profile()
        if self.settings_service is None:
            return
        normalized = "off" if str(state).strip().lower() == "off" else "on"
        self.settings_service.set_setting(
            self._power_state_key(profile),
            normalized,
        )

    def _parse_numeric_amount(self, raw_amount: str) -> float | None:
        """Parse numeric amount from free-form speech text.

        Accepts forms like '5', '5.0', '5°', '5 degrees', and words
        like 'five'. Returns None when no numeric intent is detectable.
        """
        if not raw_amount:
            return None
        normalized = raw_amount.strip().lower().replace(",", ".")
        word_amounts = {
            "zero": 0.0,
            "one": 1.0,
            "two": 2.0,
            "three": 3.0,
            "four": 4.0,
            "five": 5.0,
            "six": 6.0,
            "seven": 7.0,
            "eight": 8.0,
            "nine": 9.0,
            "ten": 10.0,
        }
        if normalized in word_amounts:
            return word_amounts[normalized]
        match = re.search(r"[-+]?\d+(?:\.\d+)?", normalized)
        if match:
            return float(match.group(0))
        return None

    def _resolve_temperature_amount(self, message, default: float = 5.0) -> float:
        """Resolve what-if temperature delta from slots or raw utterance."""
        data = getattr(message, "data", {}) or {}
        slot_amount = self._parse_numeric_amount(str(data.get("amount", "")))
        if slot_amount is not None:
            return slot_amount

        utterance = self._extract_utterance_text(message).lower()
        phrase_match = re.search(
            r"\b(?:by|to)\s+([-+]?\d+(?:[\.,]\d+)?|zero|one|two|three|four|five|six|seven|eight|nine|ten)\b",
            utterance,
        )
        if phrase_match:
            parsed = self._parse_numeric_amount(phrase_match.group(1))
            if parsed is not None:
                return parsed

        fallback_amount = self._parse_numeric_amount(utterance)
        if fallback_amount is not None:
            return fallback_amount

        return default

    def _extract_utterance_text(self, message) -> str:
        """Extract raw utterance text from message payload/context when present."""
        data = getattr(message, "data", {}) or {}
        utterance = data.get("utterance")
        if isinstance(utterance, str):
            return utterance
        utterances = data.get("utterances")
        if isinstance(utterances, list) and utterances and isinstance(utterances[0], str):
            return utterances[0]
        return ""

    def _canonicalize_asset_id(self, raw_asset: str) -> str:
        """Normalize common spoken asset forms into stable IDs."""
        token = (raw_asset or "").strip()
        if not token:
            return ""
        normalized = re.sub(r"[-_]+", " ", token.lower()).strip()
        line_match = re.fullmatch(
            r"line\s+(1|2|3|4|5|one|two|three|four|five|to|too)",
            normalized,
        )
        if not line_match:
            return token
        digits = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "to": "2", "too": "2"}
        suffix = digits.get(line_match.group(1), line_match.group(1))
        return f"Line-{suffix}"

    def _extract_line_assets_from_text(self, text: str) -> list[str]:
        """Extract spoken line assets from utterance text (e.g., line two)."""
        if not text:
            return []
        matches = re.findall(
            r"\bline\s+(1|2|3|4|5|one|two|three|four|five|to|too)\b",
            text.lower(),
        )
        return [self._canonicalize_asset_id(f"line {value}") for value in matches]

    def _resolve_asset_id(self, message, default: str = "default") -> str:
        """Resolve asset_id using slot first, then utterance fallback parsing."""
        data = getattr(message, "data", {}) or {}
        slot_asset = self._canonicalize_asset_id(str(data.get("asset", "")))
        if slot_asset and slot_asset.lower() not in {"to", "too", "for", "on", "line"}:
            return slot_asset
        utterance_assets = self._extract_line_assets_from_text(self._extract_utterance_text(message))
        if utterance_assets:
            return utterance_assets[0]
        return default

    def _resolve_compare_assets(self, message) -> tuple[str, str]:
        """Resolve comparison assets with utterance fallback for line references."""
        data = getattr(message, "data", {}) or {}
        asset_a = self._canonicalize_asset_id(str(data.get("asset_a", "")))
        asset_b = self._canonicalize_asset_id(str(data.get("asset_b", "")))
        if asset_a and asset_b:
            return asset_a, asset_b
        utterance_assets = self._extract_line_assets_from_text(self._extract_utterance_text(message))
        if len(utterance_assets) >= 2:
            return utterance_assets[0], utterance_assets[1]
        return asset_a or "Asset-1", asset_b or "Asset-2"

    def stop(self):
        """Cleanup runtime resources when skill is stopped."""
        try:
            if self.dispatcher is not None:
                import asyncio
                shutdown_coro = self.dispatcher.adapter.shutdown()
                try:
                    running_loop = asyncio.get_running_loop()
                except RuntimeError:
                    running_loop = None

                if running_loop and running_loop.is_running():
                    running_loop.create_task(shutdown_coro)
                else:
                    asyncio.run(shutdown_coro)
        except Exception as exc:
            self.log.warning("Adapter shutdown during stop() failed: %s", exc)
        finally:
            self._is_initialized = False


def create_skill():
    """OVOS entry point - creates and returns the skill instance."""
    return AVAROSSkill()
