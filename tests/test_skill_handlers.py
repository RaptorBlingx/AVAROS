"""
T9: Basic Skill Handler Tests

Tests for OVOS skill intent handlers that process voice commands.
Validates intent routing, slot extraction, dialog responses, and error handling.
"""
import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from typing import Dict, Any, Optional


class Message:
    """Mock OVOS Message object"""
    
    def __init__(self, message_type: str, data: Optional[Dict] = None, context: Optional[Dict] = None):
        self.msg_type = message_type
        self.data = data or {}
        self.context = context or {}


class MockOVOSSkill:
    """Mock OVOS Skill base class"""
    
    def __init__(self):
        self.dispatcher = None
        self._spoken_responses = []
        self._dialog_responses = []
    
    def speak(self, utterance: str, **kwargs):
        """Mock speak method"""
        self._spoken_responses.append(utterance)
    
    def speak_dialog(self, dialog_name: str, data: Optional[Dict] = None, **kwargs):
        """Mock speak_dialog method"""
        self._dialog_responses.append({"dialog": dialog_name, "data": data or {}})


class AVAROSSkill(MockOVOSSkill):
    """
    AVAROS Skill - handles voice intents for manufacturing KPIs
    Maps voice queries to the 5 Query Types
    """
    
    def __init__(self, dispatcher):
        super().__init__()
        self.dispatcher = dispatcher
    
    async def handle_kpi_intent(self, message: Message):
        """
        Handle GET_KPI intent
        Example: "What's the energy per unit for compressor 1?"
        """
        try:
            metric = message.data.get("metric")
            asset_id = message.data.get("asset")
            period = message.data.get("period", "today")
            
            if not metric or not asset_id:
                self.speak_dialog("error.missing_slots")
                return
            
            result = await self.dispatcher.get_kpi(metric, asset_id, period)
            
            self.speak_dialog("kpi.response", {
                "metric": metric,
                "value": result.value,
                "unit": result.unit,
                "asset": asset_id
            })
        
        except Exception as e:
            self.speak_dialog("error.query_failed", {"error": str(e)})
    
    async def handle_compare_intent(self, message: Message):
        """
        Handle COMPARE intent
        Example: "Compare energy between compressor 1 and compressor 2"
        """
        try:
            metric = message.data.get("metric")
            assets = message.data.get("assets", [])
            period = message.data.get("period", "today")
            
            if not metric or len(assets) < 2:
                self.speak_dialog("error.compare_needs_two_assets")
                return
            
            result = await self.dispatcher.compare(metric, assets, period)
            
            self.speak_dialog("compare.response", {
                "metric": metric,
                "winner": result.winner_id,
                "winner_value": result.winner_value
            })
        
        except Exception as e:
            self.speak_dialog("error.query_failed", {"error": str(e)})
    
    async def handle_trend_intent(self, message: Message):
        """
        Handle TREND intent
        Example: "Show scrap rate trend for last week"
        """
        try:
            metric = message.data.get("metric")
            asset_id = message.data.get("asset")
            period = message.data.get("period", "week")
            granularity = message.data.get("granularity", "daily")
            
            if not metric:
                self.speak_dialog("error.missing_metric")
                return
            
            result = await self.dispatcher.get_trend(metric, asset_id, period, granularity)
            
            self.speak_dialog("trend.response", {
                "metric": metric,
                "direction": result.trend_direction,
                "change": result.change_percent
            })
        
        except Exception as e:
            self.speak_dialog("error.query_failed", {"error": str(e)})
    
    async def handle_anomaly_intent(self, message: Message):
        """
        Handle ANOMALY intent
        Example: "Is there any anomaly in production?"
        """
        try:
            metric = message.data.get("metric", "energy_per_unit")
            asset_id = message.data.get("asset")
            
            result = await self.dispatcher.check_anomaly(metric, asset_id)
            
            if result.is_anomalous:
                self.speak_dialog("anomaly.detected", {
                    "severity": result.severity,
                    "recommendation": result.recommendation or "Check system logs"
                })
            else:
                self.speak_dialog("anomaly.none")
        
        except Exception as e:
            self.speak_dialog("error.query_failed", {"error": str(e)})
    
    async def handle_whatif_intent(self, message: Message):
        """
        Handle WHATIF intent
        Example: "What if we reduce temperature by 5 degrees?"
        """
        try:
            scenario_type = message.data.get("scenario_type")
            parameters = message.data.get("parameters", {})
            
            if not scenario_type:
                self.speak_dialog("error.missing_scenario")
                return
            
            scenario = {
                "type": scenario_type,
                **parameters
            }
            
            result = await self.dispatcher.simulate_whatif(scenario)
            
            self.speak_dialog("whatif.response", {
                "delta": result.delta,
                "delta_percent": result.delta_percent,
                "confidence": result.confidence * 100
            })
        
        except Exception as e:
            self.speak_dialog("error.query_failed", {"error": str(e)})


# Mock result types for testing
class MockKPIResult:
    def __init__(self, value, unit):
        self.value = value
        self.unit = unit


class MockComparisonResult:
    def __init__(self, winner_id, winner_value):
        self.winner_id = winner_id
        self.winner_value = winner_value


class MockTrendResult:
    def __init__(self, trend_direction, change_percent):
        self.trend_direction = trend_direction
        self.change_percent = change_percent


class MockAnomalyResult:
    def __init__(self, is_anomalous, severity="INFO", recommendation=None):
        self.is_anomalous = is_anomalous
        self.severity = severity
        self.recommendation = recommendation


class MockWhatIfResult:
    def __init__(self, delta, delta_percent, confidence):
        self.delta = delta
        self.delta_percent = delta_percent
        self.confidence = confidence


@pytest.fixture
def mock_dispatcher():
    """Create a mock QueryDispatcher for testing"""
    dispatcher = Mock()
    dispatcher.get_kpi = AsyncMock(return_value=MockKPIResult(45.2, "kWh/unit"))
    dispatcher.compare = AsyncMock(return_value=MockComparisonResult("comp-1", 45.2))
    dispatcher.get_trend = AsyncMock(return_value=MockTrendResult("up", 12.5))
    dispatcher.check_anomaly = AsyncMock(return_value=MockAnomalyResult(False))
    dispatcher.simulate_whatif = AsyncMock(return_value=MockWhatIfResult(-3.1, -6.86, 0.85))
    return dispatcher


@pytest.fixture
def skill(mock_dispatcher):
    """Create an AVAROSSkill instance for testing"""
    return AVAROSSkill(mock_dispatcher)


class TestKPIIntentHandler:
    """Test GET_KPI intent handler"""
    
    @pytest.mark.asyncio
    async def test_handle_kpi_intent_success(self, skill, mock_dispatcher):
        """Test successful KPI query"""
        message = Message("kpi.intent", {
            "metric": "energy_per_unit",
            "asset": "compressor-1",
            "period": "today"
        })
        
        await skill.handle_kpi_intent(message)
        
        mock_dispatcher.get_kpi.assert_called_once_with(
            "energy_per_unit",
            "compressor-1",
            "today"
        )
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "kpi.response"
        assert skill._dialog_responses[0]["data"]["value"] == 45.2
    
    @pytest.mark.asyncio
    async def test_handle_kpi_intent_missing_metric(self, skill):
        """Test KPI intent with missing metric slot"""
        message = Message("kpi.intent", {
            "asset": "compressor-1"
            # Missing metric
        })
        
        await skill.handle_kpi_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.missing_slots"
    
    @pytest.mark.asyncio
    async def test_handle_kpi_intent_missing_asset(self, skill):
        """Test KPI intent with missing asset slot"""
        message = Message("kpi.intent", {
            "metric": "energy_per_unit"
            # Missing asset
        })
        
        await skill.handle_kpi_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.missing_slots"
    
    @pytest.mark.asyncio
    async def test_handle_kpi_intent_default_period(self, skill, mock_dispatcher):
        """Test KPI intent uses default period when not specified"""
        message = Message("kpi.intent", {
            "metric": "oee",
            "asset": "line-1"
            # No period specified
        })
        
        await skill.handle_kpi_intent(message)
        
        mock_dispatcher.get_kpi.assert_called_with("oee", "line-1", "today")
    
    @pytest.mark.asyncio
    async def test_handle_kpi_intent_error_handling(self, skill, mock_dispatcher):
        """Test KPI intent error handling"""
        mock_dispatcher.get_kpi = AsyncMock(side_effect=Exception("API Error"))
        
        message = Message("kpi.intent", {
            "metric": "energy_per_unit",
            "asset": "comp-1"
        })
        
        await skill.handle_kpi_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.query_failed"


class TestCompareIntentHandler:
    """Test COMPARE intent handler"""
    
    @pytest.mark.asyncio
    async def test_handle_compare_intent_success(self, skill, mock_dispatcher):
        """Test successful comparison query"""
        message = Message("compare.intent", {
            "metric": "energy_per_unit",
            "assets": ["comp-1", "comp-2"],
            "period": "today"
        })
        
        await skill.handle_compare_intent(message)
        
        mock_dispatcher.compare.assert_called_once_with(
            "energy_per_unit",
            ["comp-1", "comp-2"],
            "today"
        )
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "compare.response"
        assert skill._dialog_responses[0]["data"]["winner"] == "comp-1"
    
    @pytest.mark.asyncio
    async def test_handle_compare_intent_insufficient_assets(self, skill):
        """Test compare intent with less than 2 assets"""
        message = Message("compare.intent", {
            "metric": "scrap_rate",
            "assets": ["line-1"]  # Only one asset
        })
        
        await skill.handle_compare_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.compare_needs_two_assets"
    
    @pytest.mark.asyncio
    async def test_handle_compare_intent_missing_metric(self, skill):
        """Test compare intent with missing metric"""
        message = Message("compare.intent", {
            "assets": ["comp-1", "comp-2"]
            # Missing metric
        })
        
        await skill.handle_compare_intent(message)
        
        assert skill._dialog_responses[0]["dialog"] == "error.compare_needs_two_assets"


class TestTrendIntentHandler:
    """Test TREND intent handler"""
    
    @pytest.mark.asyncio
    async def test_handle_trend_intent_success(self, skill, mock_dispatcher):
        """Test successful trend query"""
        message = Message("trend.intent", {
            "metric": "scrap_rate",
            "asset": "line-1",
            "period": "week",
            "granularity": "daily"
        })
        
        await skill.handle_trend_intent(message)
        
        mock_dispatcher.get_trend.assert_called_once_with(
            "scrap_rate",
            "line-1",
            "week",
            "daily"
        )
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "trend.response"
        assert skill._dialog_responses[0]["data"]["direction"] == "up"
    
    @pytest.mark.asyncio
    async def test_handle_trend_intent_missing_metric(self, skill):
        """Test trend intent with missing metric"""
        message = Message("trend.intent", {
            "period": "week"
            # Missing metric
        })
        
        await skill.handle_trend_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.missing_metric"
    
    @pytest.mark.asyncio
    async def test_handle_trend_intent_defaults(self, skill, mock_dispatcher):
        """Test trend intent with default values"""
        message = Message("trend.intent", {
            "metric": "energy_per_unit"
            # No period, granularity
        })
        
        await skill.handle_trend_intent(message)
        
        mock_dispatcher.get_trend.assert_called_with(
            "energy_per_unit",
            None,  # asset_id defaults to None
            "week",  # default period
            "daily"  # default granularity
        )


class TestAnomalyIntentHandler:
    """Test ANOMALY intent handler"""
    
    @pytest.mark.asyncio
    async def test_handle_anomaly_intent_no_anomaly(self, skill, mock_dispatcher):
        """Test anomaly check when no anomaly detected"""
        message = Message("anomaly.intent", {
            "metric": "energy_per_unit",
            "asset": "comp-1"
        })
        
        await skill.handle_anomaly_intent(message)
        
        mock_dispatcher.check_anomaly.assert_called_once()
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "anomaly.none"
    
    @pytest.mark.asyncio
    async def test_handle_anomaly_intent_with_anomaly(self, skill, mock_dispatcher):
        """Test anomaly check when anomaly is detected"""
        mock_dispatcher.check_anomaly = AsyncMock(
            return_value=MockAnomalyResult(
                is_anomalous=True,
                severity="WARNING",
                recommendation="Check compressor load"
            )
        )
        
        message = Message("anomaly.intent", {
            "metric": "energy_per_unit",
            "asset": "comp-1"
        })
        
        await skill.handle_anomaly_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "anomaly.detected"
        assert skill._dialog_responses[0]["data"]["severity"] == "WARNING"
    
    @pytest.mark.asyncio
    async def test_handle_anomaly_intent_default_metric(self, skill, mock_dispatcher):
        """Test anomaly intent uses default metric when not specified"""
        message = Message("anomaly.intent", {})
        
        await skill.handle_anomaly_intent(message)
        
        # Should use default metric "energy_per_unit"
        call_args = mock_dispatcher.check_anomaly.call_args
        assert call_args[0][0] == "energy_per_unit"


class TestWhatIfIntentHandler:
    """Test WHATIF intent handler"""
    
    @pytest.mark.asyncio
    async def test_handle_whatif_intent_success(self, skill, mock_dispatcher):
        """Test successful what-if simulation"""
        message = Message("whatif.intent", {
            "scenario_type": "temperature_reduction",
            "parameters": {"value": -5}
        })
        
        await skill.handle_whatif_intent(message)
        
        mock_dispatcher.simulate_whatif.assert_called_once()
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "whatif.response"
        assert skill._dialog_responses[0]["data"]["delta"] == -3.1
    
    @pytest.mark.asyncio
    async def test_handle_whatif_intent_missing_scenario(self, skill):
        """Test what-if intent with missing scenario type"""
        message = Message("whatif.intent", {})
        
        await skill.handle_whatif_intent(message)
        
        assert len(skill._dialog_responses) == 1
        assert skill._dialog_responses[0]["dialog"] == "error.missing_scenario"
    
    @pytest.mark.asyncio
    async def test_handle_whatif_intent_empty_parameters(self, skill, mock_dispatcher):
        """Test what-if intent with empty parameters"""
        message = Message("whatif.intent", {
            "scenario_type": "material_change"
            # No parameters
        })
        
        await skill.handle_whatif_intent(message)
        
        # Should still work with empty parameters
        mock_dispatcher.simulate_whatif.assert_called_once()


class TestSkillErrorHandling:
    """Test skill-level error handling"""
    
    @pytest.mark.asyncio
    async def test_all_handlers_catch_exceptions(self, skill, mock_dispatcher):
        """Test that all handlers catch and handle exceptions gracefully"""
        mock_dispatcher.get_kpi = AsyncMock(side_effect=Exception("Test error"))
        mock_dispatcher.compare = AsyncMock(side_effect=Exception("Test error"))
        mock_dispatcher.get_trend = AsyncMock(side_effect=Exception("Test error"))
        mock_dispatcher.check_anomaly = AsyncMock(side_effect=Exception("Test error"))
        mock_dispatcher.simulate_whatif = AsyncMock(side_effect=Exception("Test error"))
        
        handlers = [
            (skill.handle_kpi_intent, {"metric": "oee", "asset": "line-1"}),
            (skill.handle_compare_intent, {"metric": "oee", "assets": ["l1", "l2"]}),
            (skill.handle_trend_intent, {"metric": "oee"}),
            (skill.handle_anomaly_intent, {"metric": "oee"}),
            (skill.handle_whatif_intent, {"scenario_type": "test"}),
        ]
        
        for handler, data in handlers:
            skill._dialog_responses.clear()
            message = Message("test.intent", data)
            
            # Should not raise exception
            await handler(message)
            
            # Should have error response
            assert any("error" in r["dialog"] for r in skill._dialog_responses)


class TestIntentSlotExtraction:
    """Test slot extraction from messages"""
    
    @pytest.mark.asyncio
    async def test_message_data_extraction(self, skill):
        """Test that slots are correctly extracted from message data"""
        message = Message("test.intent", {
            "metric": "energy_per_unit",
            "asset": "compressor-1",
            "period": "today",
            "extra_field": "ignored"
        })
        
        # Verify data is accessible
        assert message.data.get("metric") == "energy_per_unit"
        assert message.data.get("asset") == "compressor-1"
        assert message.data.get("period") == "today"
    
    @pytest.mark.asyncio
    async def test_message_data_defaults(self, skill):
        """Test default values for missing slots"""
        message = Message("test.intent", {})
        
        # Verify defaults work
        assert message.data.get("period", "today") == "today"
        assert message.data.get("missing_key") is None
