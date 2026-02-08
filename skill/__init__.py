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

from typing import Callable, Any, List
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler

from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult, ComparisonResult, TrendResult, AnomalyResult, WhatIfResult
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
        
        super().__init__(*args, **kwargs)
        
        self.adapter_factory: AdapterFactory | None = None
        self.dispatcher: QueryDispatcher | None = None
        self.response_builder: ResponseBuilder | None = None

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
        
        Sets up the adapter factory and query dispatcher. By default,
        uses MockAdapter for zero-config demo deployment.
        """
        self.adapter_factory = AdapterFactory(settings_service=None)  # Will use SettingsService
        adapter = self.adapter_factory.create()
        self.dispatcher = QueryDispatcher(adapter=adapter)
        self.response_builder = ResponseBuilder(verbosity="normal")
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
