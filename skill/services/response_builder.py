"""
ResponseBuilder - Voice Response Formatting Helper

Converts canonical result types into natural, concise voice responses.
Ensures responses are under 30 words for optimal voice UX.

Features:
    - Natural language formatting
    - Number rounding and unit formatting
    - Contextual phrasing based on values
    - Support for all 5 query result types

Usage:
    builder = ResponseBuilder()
    
    # KPI result
    response = builder.format_kpi_result(kpi_result)
    # "The OEE for Line 1 is 82.5 percent today"
    
    # Comparison result
    response = builder.format_comparison_result(comparison_result)
    # "Compressor 1 is more efficient, using 0.5 kilowatt hours less energy"
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from skill.domain.results import (
        KPIResult,
        ComparisonResult,
        TrendResult,
        AnomalyResult,
        WhatIfResult,
    )
    from skill.domain.models import CanonicalMetric


class ResponseBuilder:
    """
    Build natural voice responses from canonical result types.
    
    Follows voice UX best practices:
    - Keep responses under 30 words
    - Use natural conversational language
    - Round numbers appropriately (no excess precision)
    - Include context (asset, period) when helpful
    
    Example:
        builder = ResponseBuilder()
        
        # Format KPI result
        text = builder.format_kpi_result(result)
        skill.speak(text)
    """
    
    def __init__(self, verbosity: str = "normal"):
        """
        Initialize response builder.
        
        Args:
            verbosity: Response detail level ("brief", "normal", "detailed")
        """
        self.verbosity = verbosity
    
    # =========================================================================
    # KPI Results
    # =========================================================================
    
    def format_kpi_result(self, result: KPIResult) -> str:
        """
        Format a KPI result into natural speech.
        
        Args:
            result: KPIResult to format
            
        Returns:
            Natural language description
            
        Example:
            "The OEE for Line 1 is 82.5 percent today"
            "Energy per unit for Compressor 1 is 2.3 kilowatt hours"
        """
        metric_name = result.metric.display_name
        asset_name = self._format_asset_name(result.asset_id)
        value = self._format_value(result.value, result.unit)
        period = result.period.display_name if self.verbosity != "brief" else ""
        
        if self.verbosity == "brief":
            return f"{value}"
        elif self.verbosity == "normal":
            return f"The {metric_name} for {asset_name} is {value} {period}".strip()
        else:  # detailed
            recommendation = self._get_kpi_recommendation(result)
            return f"The {metric_name} for {asset_name} is {value} {period}. {recommendation}".strip()
    
    # =========================================================================
    # Comparison Results
    # =========================================================================
    
    def format_comparison_result(self, result: ComparisonResult) -> str:
        """
        Format a comparison result.
        
        Args:
            result: ComparisonResult to format
            
        Returns:
            Natural language comparison
            
        Example:
            "Compressor 1 is more efficient, using 0.5 kilowatt hours less energy"
            "Line 1 wins with 2.3 percent better OEE"
        """
        winner = self._format_asset_name(result.winner_id)
        metric_name = result.metric.display_name
        difference = self._format_value(result.difference, result.unit)
        
        # Determine if lower or higher is better
        lower_is_better = self._is_lower_better(result.metric)
        
        if self.verbosity == "brief":
            return f"{winner} wins by {difference}"
        elif lower_is_better:
            return f"{winner} is more efficient, using {difference} less {metric_name}"
        else:
            return f"{winner} wins with {difference} better {metric_name}"
    
    # =========================================================================
    # Trend Results
    # =========================================================================
    
    def format_trend_result(self, result: TrendResult) -> str:
        """
        Format a trend result.
        
        Args:
            result: TrendResult to format
            
        Returns:
            Natural language trend description
            
        Example:
            "Scrap rate is trending down, decreasing 12.5 percent over last week"
            "Energy use went up by 8 percent"
        """
        metric_name = result.metric.display_name
        direction = result.direction
        change = abs(result.change_percent)
        period = result.period.display_name
        
        # Direction verbs
        if direction == "up":
            verb = "increasing" if self.verbosity == "normal" else "went up"
        elif direction == "down":
            verb = "decreasing" if self.verbosity == "normal" else "went down"
        else:
            verb = "stable"
        
        if self.verbosity == "brief":
            return f"{direction.capitalize()}, {change:.1f} percent"
        elif result.direction == "stable":
            return f"{metric_name} is stable over {period}"
        else:
            return f"{metric_name} is trending {direction}, {verb} {change:.1f} percent over {period}"
    
    # =========================================================================
    # Anomaly Results
    # =========================================================================
    
    def format_anomaly_result(self, result: AnomalyResult) -> str:
        """
        Format an anomaly detection result.
        
        Args:
            result: AnomalyResult to format
            
        Returns:
            Natural language anomaly description
            
        Example:
            "I found 2 anomalies with medium severity"
            "No unusual patterns detected"
        """
        if not result.is_anomalous:
            return "No unusual patterns detected. Everything looks normal."
        
        count = len(result.anomalies)
        severity = result.severity
        
        if self.verbosity == "brief":
            return f"{count} anomalies, {severity} severity"
        elif self.verbosity == "normal":
            plural = "anomalies" if count > 1 else "anomaly"
            return f"I found {count} {plural} with {severity} severity"
        else:  # detailed
            plural = "anomalies" if count > 1 else "anomaly"
            first_anomaly = result.anomalies[0] if result.anomalies else None
            description = first_anomaly.description if first_anomaly else ""
            return f"I found {count} {plural} with {severity} severity. {description}"
    
    # =========================================================================
    # What-If Results
    # =========================================================================
    
    def format_whatif_result(self, result: WhatIfResult) -> str:
        """
        Format a what-if simulation result.
        
        Args:
            result: WhatIfResult to format
            
        Returns:
            Natural language prediction
            
        Example:
            "Temperature reduction could change energy from 2.8 to 2.2, that's 20 percent savings"
            "Projected savings of 15 percent with high confidence"
        """
        metric_name = result.target_metric.display_name
        baseline = self._format_value(result.baseline, result.unit)
        projected = self._format_value(result.projected, result.unit)
        change = abs(result.delta_percent)
        
        # Determine if change is improvement
        if result.is_improvement:
            change_word = "savings" if result.delta < 0 else "improvement"
        else:
            change_word = "increase" if result.delta > 0 else "decrease"
        
        confidence_pct = int(result.confidence * 100)
        confidence_level = result.confidence_level
        
        if self.verbosity == "brief":
            return f"{change:.1f} percent {change_word}"
        elif self.verbosity == "normal":
            return f"The simulation shows {metric_name} would change from {baseline} to {projected}, about {change:.1f} percent {change_word}"
        else:  # detailed
            return f"If you proceed, {metric_name} would go from {baseline} to {projected}. That's {change:.1f} percent {change_word} with {confidence_level} confidence ({confidence_pct} percent)"
    
    # =========================================================================
    # Helper Methods
    # =========================================================================
    
    def _format_asset_name(self, asset_id: str) -> str:
        """Format asset ID into natural speech."""
        # Convert "Line-1" → "Line 1", "Compressor-2" → "Compressor 2"
        return asset_id.replace("-", " ").replace("_", " ")
    
    def _format_value(self, value: float, unit: str) -> str:
        """Format numeric value with appropriate precision."""
        # Round to 1 decimal place for most metrics
        if unit == "%":
            return f"{value:.1f} percent"
        elif "kWh" in unit:
            return f"{value:.1f} kilowatt hours"
        elif "kg" in unit:
            return f"{value:.1f} kilograms"
        elif "°C" in unit:
            return f"{value:.1f} degrees celsius"
        elif unit in ("sec", "seconds"):
            return f"{value:.1f} seconds"
        elif unit in ("min", "minutes"):
            return f"{value:.1f} minutes"
        elif unit in ("days",):
            return f"{value:.1f} days"
        else:
            return f"{value:.1f} {unit.lower()}"
    
    def _is_lower_better(self, metric: CanonicalMetric) -> bool:
        """Determine if lower values are better for this metric."""
        from skill.domain.models import CanonicalMetric
        
        # Metrics where higher is better
        higher_is_better = {
            CanonicalMetric.OEE,
            CanonicalMetric.MATERIAL_EFFICIENCY,
            CanonicalMetric.THROUGHPUT,
            CanonicalMetric.SUPPLIER_ON_TIME,
            CanonicalMetric.RECYCLED_CONTENT,
        }
        
        return metric not in higher_is_better
    
    def _get_kpi_recommendation(self, result: KPIResult) -> str:
        """Generate simple recommendation based on KPI value."""
        from skill.domain.models import CanonicalMetric
        
        # Simple heuristics for recommendations
        if result.metric == CanonicalMetric.OEE:
            if result.value < 70:
                return "This is below industry average. Consider investigating bottlenecks."
            elif result.value > 85:
                return "This is excellent performance."
        elif result.metric == CanonicalMetric.SCRAP_RATE:
            if result.value > 5:
                return "Scrap rate is high. Review quality controls."
            elif result.value < 2:
                return "Scrap rate is excellent."
        
        return ""
