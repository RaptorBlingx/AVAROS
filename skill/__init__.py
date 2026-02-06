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

from typing import Callable, Any
from ovos_workshop.skills import OVOSSkill
from ovos_workshop.decorators import intent_handler

from skill.domain.models import CanonicalMetric, TimePeriod
from skill.domain.results import KPIResult, ComparisonResult, TrendResult, AnomalyResult, WhatIfResult
from skill.use_cases.query_dispatcher import QueryDispatcher
from skill.adapters.factory import AdapterFactory


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

    def initialize(self):
        """
        Called after the skill is fully constructed and registered.
        
        Sets up the adapter factory and query dispatcher. By default,
        uses MockAdapter for zero-config demo deployment.
        """
        self.adapter_factory = AdapterFactory(settings_service=None)  # Will use SettingsService
        adapter = self.adapter_factory.create()
        self.dispatcher = QueryDispatcher(adapter=adapter)
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
            
            self.speak_dialog(
                "kpi.energy.response",
                data={
                    "asset_name": result.asset_id,
                    "value": f"{result.value:.2f}",
                    "unit": result.unit,
                    "period": result.period.display_name
                }
            )
        
        self._safe_dispatch("handle_kpi_energy_per_unit", _execute)

    @intent_handler("kpi.oee.intent")
    def handle_kpi_oee(self, message):
        """Handle: 'What's the OEE for {asset}?'"""
        asset_id = message.data.get("asset", "default")
        period = self._parse_period(message.data.get("period", "today"))
        
        result: KPIResult = self.dispatcher.get_kpi(
            metric=CanonicalMetric.OEE,
            asset_id=asset_id,
            period=period
        )
        
        self.speak_dialog(
            "kpi.oee.response",
            data={
                "asset_name": result.asset_id,
                "value": f"{result.value:.1f}",
                "unit": result.unit,
                "period": result.period.display_name
            }
        )

    @intent_handler("kpi.scrap_rate.intent")
    def handle_kpi_scrap_rate(self, message):
        """Handle: 'What's the scrap rate?'"""
        asset_id = message.data.get("asset", "default")
        period = self._parse_period(message.data.get("period", "today"))
        
        result: KPIResult = self.dispatcher.get_kpi(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id=asset_id,
            period=period
        )
        
        self.speak_dialog(
            "kpi.scrap_rate.response",
            data={
                "asset_name": result.asset_id,
                "value": f"{result.value:.2f}",
                "unit": result.unit,
                "period": result.period.display_name
            }
        )

    # =========================================================================
    # Compare Query Handlers
    # =========================================================================
    
    @intent_handler("compare.energy.intent")
    def handle_compare_energy(self, message):
        """Handle: 'Compare energy between {asset_a} and {asset_b}'"""
        asset_a = message.data.get("asset_a", "Asset-1")
        asset_b = message.data.get("asset_b", "Asset-2")
        period = self._parse_period(message.data.get("period", "today"))
        
        result: ComparisonResult = self.dispatcher.compare(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_ids=[asset_a, asset_b],
            period=period
        )
        
        self.speak_dialog(
            "compare.energy.response",
            data={
                "winner": result.winner_id,
                "metric": "energy per unit",
                "difference": f"{abs(result.difference):.1f}",
                "unit": result.unit
            }
        )

    # =========================================================================
    # Trend Query Handlers
    # =========================================================================
    
    @intent_handler("trend.scrap.intent")
    def handle_trend_scrap(self, message):
        """Handle: 'Show scrap rate trend for {period}'"""
        asset_id = message.data.get("asset", "default")
        period = self._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")
        
        result: TrendResult = self.dispatcher.get_trend(
            metric=CanonicalMetric.SCRAP_RATE,
            asset_id=asset_id,
            period=period,
            granularity=granularity
        )
        
        self.speak_dialog(
            "trend.scrap.response",
            data={
                "direction": result.direction,
                "change_percent": f"{result.change_percent:.1f}",
                "period": period.display_name
            }
        )

    @intent_handler("trend.energy.intent")
    def handle_trend_energy(self, message):
        """Handle: 'Show energy trend for {period}'"""
        asset_id = message.data.get("asset", "default")
        period = self._parse_period(message.data.get("period", "last week"))
        granularity = message.data.get("granularity", "daily")
        
        result: TrendResult = self.dispatcher.get_trend(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            asset_id=asset_id,
            period=period,
            granularity=granularity
        )
        
        self.speak_dialog(
            "trend.energy.response",
            data={
                "direction": result.direction,
                "change_percent": f"{result.change_percent:.1f}",
                "period": period.display_name
            }
        )

    # =========================================================================
    # Anomaly Query Handlers
    # =========================================================================
    
    @intent_handler("anomaly.production.check.intent")
    def handle_anomaly_check(self, message):
        """Handle: 'Any unusual patterns in production?'"""
        asset_id = message.data.get("asset", "default")
        
        result: AnomalyResult = self.dispatcher.check_anomaly(
            metric=CanonicalMetric.OEE,
            asset_id=asset_id
        )
        
        if result.is_anomalous:
            self.speak_dialog(
                "anomaly.found.response",
                data={
                    "count": len(result.anomalies),
                    "severity": result.severity,
                    "description": result.anomalies[0].description if result.anomalies else ""
                }
            )
        else:
            self.speak_dialog("anomaly.none.response")

    # =========================================================================
    # What-If Query Handlers
    # =========================================================================
    
    @intent_handler("whatif.temperature.intent")
    def handle_whatif_temperature(self, message):
        """Handle: 'What if we reduce temperature by {amount} degrees?'"""
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
        
        self.speak_dialog(
            "whatif.temperature.response",
            data={
                "baseline": f"{result.baseline:.1f}",
                "projected": f"{result.projected:.1f}",
                "delta_percent": f"{result.delta_percent:.1f}",
                "confidence": f"{result.confidence * 100:.0f}"
            }
        )

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
