"""
T5: Result Type Validation Tests

Tests for canonical manufacturing data model types (KPIResult, ComparisonResult, etc.)
Validates type structure, immutability, serialization, and field constraints.
"""
import pytest
from dataclasses import dataclass, FrozenInstanceError
from datetime import datetime
from typing import List, Dict, Optional, Literal
from enum import Enum


class CanonicalMetric(Enum):
    """Canonical metrics that AVAROS understands"""
    ENERGY_PER_UNIT = "energy_per_unit"
    ENERGY_TOTAL = "energy_total"
    PEAK_DEMAND = "peak_demand"
    SCRAP_RATE = "scrap_rate"
    REWORK_RATE = "rework_rate"
    MATERIAL_EFFICIENCY = "material_efficiency"
    SUPPLIER_LEAD_TIME = "supplier_lead_time"
    SUPPLIER_DEFECT_RATE = "supplier_defect_rate"
    SUPPLIER_ON_TIME = "supplier_on_time"
    OEE = "oee"
    THROUGHPUT = "throughput"
    CYCLE_TIME = "cycle_time"
    CO2_PER_UNIT = "co2_per_unit"
    CO2_TOTAL = "co2_total"


@dataclass(frozen=True)
class KPIResult:
    """Result type for GET_KPI query"""
    metric: CanonicalMetric
    value: float
    unit: str
    timestamp: datetime
    asset_id: str
    period: str
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'KPIResult':
        """Deserialize from dictionary"""
        return cls(
            metric=CanonicalMetric(data['metric']) if isinstance(data['metric'], str) else data['metric'],
            value=float(data['value']),
            unit=data['unit'],
            timestamp=data['timestamp'] if isinstance(data['timestamp'], datetime) else datetime.fromisoformat(data['timestamp']),
            asset_id=data['asset_id'],
            period=data['period']
        )


@dataclass(frozen=True)
class ComparisonResult:
    """Result type for COMPARE query"""
    metric: CanonicalMetric
    items: List[Dict]
    winner_id: str
    winner_value: float
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'ComparisonResult':
        """Deserialize from dictionary"""
        return cls(
            metric=CanonicalMetric(data['metric']) if isinstance(data['metric'], str) else data['metric'],
            items=data['items'],
            winner_id=data['winner_id'],
            winner_value=float(data['winner_value'])
        )


@dataclass(frozen=True)
class DataPoint:
    """Single data point in a trend"""
    timestamp: datetime
    value: float


@dataclass(frozen=True)
class TrendResult:
    """Result type for TREND query"""
    metric: CanonicalMetric
    data_points: List[DataPoint]
    trend_direction: Literal['up', 'down', 'stable']
    change_percent: float
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'TrendResult':
        """Deserialize from dictionary"""
        return cls(
            metric=CanonicalMetric(data['metric']) if isinstance(data['metric'], str) else data['metric'],
            data_points=[
                DataPoint(
                    timestamp=dp['timestamp'] if isinstance(dp['timestamp'], datetime) else datetime.fromisoformat(dp['timestamp']),
                    value=float(dp['value'])
                )
                for dp in data['data_points']
            ],
            trend_direction=data['trend_direction'],
            change_percent=float(data['change_percent'])
        )


@dataclass(frozen=True)
class AnomalyDetail:
    """Details of a single anomaly"""
    timestamp: datetime
    value: float
    expected: float
    deviation_sigma: float


@dataclass(frozen=True)
class AnomalyResult:
    """Result type for ANOMALY query"""
    is_anomalous: bool
    anomalies: List[AnomalyDetail]
    severity: Literal['INFO', 'WARNING', 'CRITICAL']
    recommendation: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'AnomalyResult':
        """Deserialize from dictionary"""
        return cls(
            is_anomalous=bool(data['is_anomalous']),
            anomalies=[
                AnomalyDetail(
                    timestamp=a['timestamp'] if isinstance(a['timestamp'], datetime) else datetime.fromisoformat(a['timestamp']),
                    value=float(a['value']),
                    expected=float(a['expected']),
                    deviation_sigma=float(a['deviation_sigma'])
                )
                for a in data['anomalies']
            ],
            severity=data['severity'],
            recommendation=data.get('recommendation')
        )


@dataclass(frozen=True)
class WhatIfResult:
    """Result type for WHATIF query"""
    scenario_id: str
    baseline: Dict
    projected: Dict
    delta: float
    delta_percent: float
    confidence: float
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'WhatIfResult':
        """Deserialize from dictionary"""
        return cls(
            scenario_id=data['scenario_id'],
            baseline=data['baseline'],
            projected=data['projected'],
            delta=float(data['delta']),
            delta_percent=float(data['delta_percent']),
            confidence=float(data['confidence'])
        )


class TestCanonicalMetric:
    """Test CanonicalMetric enum"""
    
    def test_all_metrics_defined(self):
        """Test that all required metrics are defined"""
        required_metrics = [
            'ENERGY_PER_UNIT', 'ENERGY_TOTAL', 'PEAK_DEMAND',
            'SCRAP_RATE', 'REWORK_RATE', 'MATERIAL_EFFICIENCY',
            'SUPPLIER_LEAD_TIME', 'SUPPLIER_DEFECT_RATE', 'SUPPLIER_ON_TIME',
            'OEE', 'THROUGHPUT', 'CYCLE_TIME',
            'CO2_PER_UNIT', 'CO2_TOTAL'
        ]
        
        for metric_name in required_metrics:
            assert hasattr(CanonicalMetric, metric_name)
    
    def test_metric_values_are_snake_case(self):
        """Test that metric values follow snake_case convention"""
        for metric in CanonicalMetric:
            assert metric.value.islower()
            assert '_' in metric.value or len(metric.value.split('_')) == 1


class TestKPIResult:
    """Test KPIResult dataclass"""
    
    def test_kpi_result_creation(self, mock_kpi_data):
        """Test creating a KPIResult instance"""
        result = KPIResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            value=45.2,
            unit="kWh/unit",
            timestamp=datetime.now(),
            asset_id="compressor-1",
            period="today"
        )
        
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.value == 45.2
        assert result.unit == "kWh/unit"
        assert result.asset_id == "compressor-1"
    
    def test_kpi_result_is_immutable(self):
        """Test that KPIResult is frozen (immutable)"""
        result = KPIResult(
            metric=CanonicalMetric.OEE,
            value=82.5,
            unit="%",
            timestamp=datetime.now(),
            asset_id="line-1",
            period="today"
        )
        
        with pytest.raises(FrozenInstanceError):
            result.value = 90.0
    
    def test_kpi_result_from_dict(self):
        """Test deserializing KPIResult from dictionary"""
        data = {
            'metric': 'energy_per_unit',
            'value': 45.2,
            'unit': 'kWh/unit',
            'timestamp': datetime.now().isoformat(),
            'asset_id': 'compressor-1',
            'period': 'today'
        }
        
        result = KPIResult.from_dict(data)
        
        assert isinstance(result, KPIResult)
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert result.value == 45.2


class TestComparisonResult:
    """Test ComparisonResult dataclass"""
    
    def test_comparison_result_creation(self):
        """Test creating a ComparisonResult instance"""
        result = ComparisonResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            items=[
                {"id": "comp-1", "value": 45.2, "unit": "kWh/unit"},
                {"id": "comp-2", "value": 52.3, "unit": "kWh/unit"}
            ],
            winner_id="comp-1",
            winner_value=45.2
        )
        
        assert result.metric == CanonicalMetric.ENERGY_PER_UNIT
        assert len(result.items) == 2
        assert result.winner_id == "comp-1"
    
    def test_comparison_result_is_immutable(self):
        """Test that ComparisonResult is frozen"""
        result = ComparisonResult(
            metric=CanonicalMetric.SCRAP_RATE,
            items=[{"id": "line-1", "value": 3.1}],
            winner_id="line-1",
            winner_value=3.1
        )
        
        with pytest.raises(FrozenInstanceError):
            result.winner_id = "line-2"
    
    def test_comparison_result_from_dict(self, mock_comparison_data):
        """Test deserializing ComparisonResult from dictionary"""
        result = ComparisonResult.from_dict(mock_comparison_data)
        
        assert isinstance(result, ComparisonResult)
        assert result.winner_id == "compressor-1"


class TestTrendResult:
    """Test TrendResult dataclass"""
    
    def test_trend_result_creation(self):
        """Test creating a TrendResult instance"""
        data_points = [
            DataPoint(timestamp=datetime.now(), value=3.1),
            DataPoint(timestamp=datetime.now(), value=3.2),
            DataPoint(timestamp=datetime.now(), value=3.4)
        ]
        
        result = TrendResult(
            metric=CanonicalMetric.SCRAP_RATE,
            data_points=data_points,
            trend_direction='up',
            change_percent=9.7
        )
        
        assert result.metric == CanonicalMetric.SCRAP_RATE
        assert len(result.data_points) == 3
        assert result.trend_direction == 'up'
    
    def test_trend_result_is_immutable(self):
        """Test that TrendResult is frozen"""
        result = TrendResult(
            metric=CanonicalMetric.ENERGY_PER_UNIT,
            data_points=[],
            trend_direction='stable',
            change_percent=0.0
        )
        
        with pytest.raises(FrozenInstanceError):
            result.trend_direction = 'up'
    
    def test_data_point_is_immutable(self):
        """Test that DataPoint is frozen"""
        dp = DataPoint(timestamp=datetime.now(), value=45.2)
        
        with pytest.raises(FrozenInstanceError):
            dp.value = 50.0
    
    def test_trend_direction_values(self):
        """Test that trend_direction only accepts valid values"""
        valid_directions = ['up', 'down', 'stable']
        
        for direction in valid_directions:
            result = TrendResult(
                metric=CanonicalMetric.OEE,
                data_points=[],
                trend_direction=direction,
                change_percent=0.0
            )
            assert result.trend_direction == direction


class TestAnomalyResult:
    """Test AnomalyResult dataclass"""
    
    def test_anomaly_result_creation(self):
        """Test creating an AnomalyResult instance"""
        anomalies = [
            AnomalyDetail(
                timestamp=datetime.now(),
                value=67.8,
                expected=45.2,
                deviation_sigma=3.2
            )
        ]
        
        result = AnomalyResult(
            is_anomalous=True,
            anomalies=anomalies,
            severity='WARNING',
            recommendation="Check compressor load"
        )
        
        assert result.is_anomalous is True
        assert len(result.anomalies) == 1
        assert result.severity == 'WARNING'
    
    def test_anomaly_result_is_immutable(self):
        """Test that AnomalyResult is frozen"""
        result = AnomalyResult(
            is_anomalous=False,
            anomalies=[],
            severity='INFO'
        )
        
        with pytest.raises(FrozenInstanceError):
            result.is_anomalous = True
    
    def test_anomaly_detail_is_immutable(self):
        """Test that AnomalyDetail is frozen"""
        detail = AnomalyDetail(
            timestamp=datetime.now(),
            value=67.8,
            expected=45.2,
            deviation_sigma=3.2
        )
        
        with pytest.raises(FrozenInstanceError):
            detail.value = 70.0
    
    def test_severity_levels(self):
        """Test that severity accepts valid levels"""
        valid_levels = ['INFO', 'WARNING', 'CRITICAL']
        
        for level in valid_levels:
            result = AnomalyResult(
                is_anomalous=True,
                anomalies=[],
                severity=level
            )
            assert result.severity == level


class TestWhatIfResult:
    """Test WhatIfResult dataclass"""
    
    def test_whatif_result_creation(self):
        """Test creating a WhatIfResult instance"""
        result = WhatIfResult(
            scenario_id="temperature_reduction",
            baseline={"value": 45.2, "unit": "kWh/unit"},
            projected={"value": 42.1, "unit": "kWh/unit"},
            delta=-3.1,
            delta_percent=-6.86,
            confidence=0.85
        )
        
        assert result.scenario_id == "temperature_reduction"
        assert result.delta == -3.1
        assert result.confidence == 0.85
    
    def test_whatif_result_is_immutable(self):
        """Test that WhatIfResult is frozen"""
        result = WhatIfResult(
            scenario_id="test",
            baseline={},
            projected={},
            delta=0.0,
            delta_percent=0.0,
            confidence=0.5
        )
        
        with pytest.raises(FrozenInstanceError):
            result.confidence = 0.9
    
    def test_whatif_result_from_dict(self, mock_whatif_data):
        """Test deserializing WhatIfResult from dictionary"""
        result = WhatIfResult.from_dict(mock_whatif_data)
        
        assert isinstance(result, WhatIfResult)
        assert result.scenario_id == "temperature_reduction"
        assert result.confidence == 0.85


class TestResultTypeIntegration:
    """Integration tests for result types"""
    
    def test_all_result_types_are_frozen(self):
        """Test that all result types are immutable"""
        result_classes = [
            KPIResult,
            ComparisonResult,
            TrendResult,
            AnomalyResult,
            WhatIfResult
        ]
        
        for cls in result_classes:
            assert cls.__dataclass_params__.frozen is True
    
    def test_all_result_types_have_from_dict(self):
        """Test that all result types have from_dict method"""
        result_classes = [
            KPIResult,
            ComparisonResult,
            TrendResult,
            AnomalyResult,
            WhatIfResult
        ]
        
        for cls in result_classes:
            assert hasattr(cls, 'from_dict')
            assert callable(getattr(cls, 'from_dict'))
