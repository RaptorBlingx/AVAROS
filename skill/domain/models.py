"""
Canonical Manufacturing Domain Models

These models define the universal manufacturing concepts that AVAROS understands.
They are platform-agnostic and immutable (frozen dataclasses).

Usage:
    All adapters must convert platform-specific responses INTO these types.
    Intent handlers work ONLY with these canonical types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import calendar
import re
from typing import Any, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


class CanonicalMetric(Enum):
    """
    Universal manufacturing metrics that AVAROS understands.
    
    These are the "language" of AVAROS. Platform adapters map their
    specific metric names to these canonical values.
    
    Categories:
        - Energy: Power consumption and efficiency
        - Material: Waste and efficiency tracking
        - Supplier: Supply chain performance
        - Production: Manufacturing performance
        - Carbon: Environmental impact
    """
    
    # Energy Metrics
    ENERGY_PER_UNIT = "energy_per_unit"       # kWh per unit produced
    ENERGY_TOTAL = "energy_total"             # Total kWh consumed
    PEAK_DEMAND = "peak_demand"               # Maximum power draw (kW)
    PEAK_TARIFF_EXPOSURE = "peak_tariff_exposure"  # Cost exposure to peak rates
    CONSUMPTION_POWER = "consumption_power"   # Instantaneous electrical consumption
    PRODUCTION_POWER = "production_power"     # Instantaneous electrical production
    ENERGY_PRODUCTION_TOTAL = "energy_production_total"  # Accumulated generated energy
    GRID_POWER = "grid_power"                 # Instantaneous grid import/export power
    ENERGY_GRID_IMPORT_TOTAL = "energy_grid_import_total"  # Accumulated grid import
    ENERGY_GRID_EXPORT_TOTAL = "energy_grid_export_total"  # Accumulated grid export
    STORAGE_STATE_OF_CHARGE = "storage_state_of_charge"  # Battery state of charge
    STORAGE_POWER = "storage_power"           # Battery charge/discharge power
    
    # Material Metrics
    SCRAP_RATE = "scrap_rate"                 # % of material scrapped
    REWORK_RATE = "rework_rate"               # % requiring rework
    MATERIAL_EFFICIENCY = "material_efficiency"  # % of input that becomes output
    RECYCLED_CONTENT = "recycled_content"     # % of recycled material used
    
    # Supplier Metrics
    SUPPLIER_LEAD_TIME = "supplier_lead_time"     # Days from order to delivery
    SUPPLIER_DEFECT_RATE = "supplier_defect_rate" # % defective from supplier
    SUPPLIER_ON_TIME = "supplier_on_time"         # % of on-time deliveries
    SUPPLIER_CO2_PER_KG = "supplier_co2_per_kg"   # CO2 per kg of material
    
    # Production Metrics
    OEE = "oee"                               # Overall Equipment Effectiveness %
    THROUGHPUT = "throughput"                 # Units per hour
    CYCLE_TIME = "cycle_time"                 # Seconds per unit
    CHANGEOVER_TIME = "changeover_time"       # Minutes for product changeover
    
    # Carbon Metrics
    CO2_PER_UNIT = "co2_per_unit"             # kg CO2-eq per unit
    CO2_TOTAL = "co2_total"                   # Total kg CO2-eq
    CO2_PER_BATCH = "co2_per_batch"           # kg CO2-eq per batch
    
    @classmethod
    def from_string(cls, value: str) -> CanonicalMetric:
        """
        Parse a string into a CanonicalMetric, supporting common aliases.
        
        Args:
            value: Metric name or alias (case-insensitive)
            
        Returns:
            Matching CanonicalMetric
            
        Raises:
            ValueError: If no matching metric found
        """
        # Normalize input
        normalized = value.lower().strip().replace(" ", "_").replace("-", "_")
        
        # Try direct enum match
        for metric in cls:
            if metric.value == normalized:
                return metric
        
        # Common aliases
        aliases = {
            "energy": cls.ENERGY_PER_UNIT,
            "power": cls.ENERGY_PER_UNIT,
            "electricity": cls.ENERGY_PER_UNIT,
            "scrap": cls.SCRAP_RATE,
            "waste": cls.SCRAP_RATE,
            "efficiency": cls.MATERIAL_EFFICIENCY,
            "oee": cls.OEE,
            "overall_equipment_effectiveness": cls.OEE,
            "carbon": cls.CO2_PER_UNIT,
            "co2": cls.CO2_PER_UNIT,
            "emissions": cls.CO2_PER_UNIT,
            "lead_time": cls.SUPPLIER_LEAD_TIME,
        }
        
        if normalized in aliases:
            return aliases[normalized]
        
        raise ValueError(f"Unknown metric: {value}")
    
    @property
    def display_name(self) -> str:
        """Human-readable name for voice responses."""
        names = {
            self.ENERGY_PER_UNIT: "energy per unit",
            self.ENERGY_TOTAL: "total energy",
            self.PEAK_DEMAND: "peak demand",
            self.CONSUMPTION_POWER: "consumption power",
            self.PRODUCTION_POWER: "production power",
            self.ENERGY_PRODUCTION_TOTAL: "total production energy",
            self.GRID_POWER: "grid power",
            self.ENERGY_GRID_IMPORT_TOTAL: "total grid import energy",
            self.ENERGY_GRID_EXPORT_TOTAL: "total grid export energy",
            self.STORAGE_STATE_OF_CHARGE: "battery state of charge",
            self.STORAGE_POWER: "battery power",
            self.SCRAP_RATE: "scrap rate",
            self.REWORK_RATE: "rework rate",
            self.MATERIAL_EFFICIENCY: "material efficiency",
            self.OEE: "overall equipment effectiveness",
            self.THROUGHPUT: "throughput",
            self.CYCLE_TIME: "cycle time",
            self.CO2_PER_UNIT: "carbon per unit",
            self.CO2_TOTAL: "total carbon emissions",
        }
        return names.get(self, self.value.replace("_", " "))
    
    @property
    def default_unit(self) -> str:
        """Default unit of measurement for this metric."""
        units = {
            self.ENERGY_PER_UNIT: "kWh/unit",
            self.ENERGY_TOTAL: "kWh",
            self.PEAK_DEMAND: "kW",
            self.CONSUMPTION_POWER: "W",
            self.PRODUCTION_POWER: "W",
            self.ENERGY_PRODUCTION_TOTAL: "Wh",
            self.GRID_POWER: "W",
            self.ENERGY_GRID_IMPORT_TOTAL: "Wh",
            self.ENERGY_GRID_EXPORT_TOTAL: "Wh",
            self.STORAGE_STATE_OF_CHARGE: "%",
            self.STORAGE_POWER: "W",
            self.PEAK_TARIFF_EXPOSURE: "%",
            self.SCRAP_RATE: "%",
            self.REWORK_RATE: "%",
            self.MATERIAL_EFFICIENCY: "%",
            self.RECYCLED_CONTENT: "%",
            self.SUPPLIER_LEAD_TIME: "days",
            self.SUPPLIER_DEFECT_RATE: "%",
            self.SUPPLIER_ON_TIME: "%",
            self.SUPPLIER_CO2_PER_KG: "kg CO₂/kg",
            self.OEE: "%",
            self.THROUGHPUT: "units/hr",
            self.CYCLE_TIME: "sec",
            self.CHANGEOVER_TIME: "min",
            self.CO2_PER_UNIT: "kg CO₂-eq/unit",
            self.CO2_TOTAL: "kg CO₂-eq",
            self.CO2_PER_BATCH: "kg CO₂-eq/batch",
        }
        return units.get(self, "")


_VALID_ASSET_TYPES = {"machine", "line", "sensor", "seu", "supplier", "group"}


@dataclass(frozen=True)
class Asset:
    """Immutable platform-agnostic asset descriptor."""

    asset_id: str
    display_name: str
    asset_type: str
    aliases: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate asset identity and type."""
        if not self.asset_id.strip():
            raise ValueError("asset_id must be non-empty")
        if self.asset_type not in _VALID_ASSET_TYPES:
            valid_types = ", ".join(sorted(_VALID_ASSET_TYPES))
            raise ValueError(
                f"Invalid asset_type '{self.asset_type}'. Must be one of: {valid_types}",
            )


@dataclass(frozen=True)
class TimePeriod:
    """
    Immutable value object representing a time range for queries.
    
    Attributes:
        start: Beginning of the period
        end: Exclusive end of the period
        display_name: Human-readable name (e.g., "today", "last week")
    """
    
    start: datetime
    end: datetime
    display_name: str = ""
    
    def __post_init__(self):
        """Validate period."""
        if self.start > self.end:
            raise ValueError(f"Start ({self.start}) must be before end ({self.end})")
    
    @classmethod
    def today(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for today."""
        now = (now or datetime.now(timezone.utc)).astimezone(cls._resolve_timezone(timezone_name))
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start.astimezone(timezone.utc), end=now.astimezone(timezone.utc), display_name="today")

    @classmethod
    def yesterday(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for the previous calendar day."""
        today_start = (now or datetime.now(timezone.utc)).astimezone(cls._resolve_timezone(timezone_name)).replace(
            hour=0, minute=0, second=0, microsecond=0,
        )
        start = today_start - timedelta(days=1)
        return cls(start=start.astimezone(timezone.utc), end=today_start.astimezone(timezone.utc), display_name="yesterday")
    
    @classmethod
    def this_week(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for the current week (Monday to now)."""
        now = (now or datetime.now(timezone.utc)).astimezone(cls._resolve_timezone(timezone_name))
        start = now - timedelta(days=now.weekday())
        start = start.replace(hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start.astimezone(timezone.utc), end=now.astimezone(timezone.utc), display_name="this week")

    @classmethod
    def this_month(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for the current month."""
        now = (now or datetime.now(timezone.utc)).astimezone(cls._resolve_timezone(timezone_name))
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls(start=start.astimezone(timezone.utc), end=now.astimezone(timezone.utc), display_name="this month")
    
    @classmethod
    def last_week(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for the previous week."""
        now = (now or datetime.now(timezone.utc)).astimezone(cls._resolve_timezone(timezone_name))
        end = now - timedelta(days=now.weekday())
        end = end.replace(hour=0, minute=0, second=0, microsecond=0)
        start = end - timedelta(days=7)
        return cls(start=start.astimezone(timezone.utc), end=end.astimezone(timezone.utc), display_name="last week")

    @classmethod
    def last_two_weeks(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a period for the last 14 days."""
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        start = now - timedelta(days=14)
        return cls(start=start.astimezone(timezone.utc), end=now.astimezone(timezone.utc), display_name="last 2 weeks")

    @classmethod
    def last_four_weeks(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create a rolling period for the last 28 days."""
        now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
        return cls(
            start=now - timedelta(days=28),
            end=now,
            display_name="last 4 weeks",
        )
    
    @classmethod
    def last_month(
        cls,
        *,
        now: datetime | None = None,
        timezone_name: str = "UTC",
    ) -> TimePeriod:
        """Create the previous calendar month in the configured site timezone."""
        tz = cls._resolve_timezone(timezone_name)
        local_now = (now or datetime.now(tz=tz)).astimezone(tz)
        this_month = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_day = this_month - timedelta(days=1)
        start = previous_day.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        return cls(
            start=start.astimezone(timezone.utc),
            end=this_month.astimezone(timezone.utc),
            display_name="last month",
        )

    @classmethod
    def rolling_days(cls, days: int, *, now: datetime | None = None) -> TimePeriod:
        """Create a rolling period ending now."""
        if days <= 0:
            raise ValueError("Rolling period must contain at least one day")
        end = now or datetime.now(timezone.utc)
        if end.tzinfo is None:
            end = end.replace(tzinfo=timezone.utc)
        return cls(
            start=end.astimezone(timezone.utc) - timedelta(days=days),
            end=end.astimezone(timezone.utc),
            display_name=f"past {days} days",
        )

    @classmethod
    def latest(cls, *, now: datetime | None = None, timezone_name: str = "UTC") -> TimePeriod:
        """Create the bounded lookup window used for latest-observation queries."""
        return cls(
            start=datetime(2021, 2, 1, tzinfo=timezone.utc),
            end=(now or datetime.now(timezone.utc)).astimezone(timezone.utc),
            display_name="latest available",
        )

    @classmethod
    def wide_default(cls) -> TimePeriod:
        """Backward-compatible alias for an explicit latest-observation lookup."""
        return cls.latest()
    
    @classmethod
    def from_natural_language(
        cls,
        text: str,
        *,
        timezone_name: str = "UTC",
        now: datetime | None = None,
    ) -> TimePeriod:
        """
        Parse natural language period description.
        
        Args:
            text: Natural language like "today", "last week", "past 3 months"
            
        Returns:
            Corresponding TimePeriod
        """
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            raise ValueError("The request clock must include a timezone")
        normalized = re.sub(r"\s+", " ", text.lower().strip())
        if not normalized:
            raise ValueError("Time period cannot be empty")

        numeric_days = re.fullmatch(
            r"(?:last|past|son) (\d+) (days|gün|gun|weeks|hafta)", normalized
        )
        if numeric_days:
            days = int(numeric_days.group(1)) * (7 if numeric_days.group(2) in {"weeks", "hafta"} else 1)
            if not 1 <= days <= 3660:
                raise ValueError("The day count must be between 1 and 3660")
            return cls._with_display_name(cls.rolling_days(days, now=now), normalized)
        if normalized in {"this year", "bu yıl", "bu yil"} or re.fullmatch(
            r"(?:19|20)\d{2}", normalized
        ):
            tz = cls._resolve_timezone(timezone_name)
            year = (
                (now or datetime.now(tz)).astimezone(tz).year
                if normalized in {"this year", "bu yıl", "bu yil"}
                else int(normalized)
            )
            start = datetime(year, 1, 1, tzinfo=tz)
            cls._reject_future(start, now=now, tz=tz)
            return cls(
                start.astimezone(timezone.utc),
                datetime(year + 1, 1, 1, tzinfo=tz).astimezone(timezone.utc),
                normalized,
            )
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", normalized):
            return cls._with_display_name(
                cls._explicit_date_range(
                    normalized, normalized, timezone_name=timezone_name, now=now
                ),
                normalized,
            )

        mapping = {
            "today": lambda: cls.today(now=now, timezone_name=timezone_name),
            "yesterday": lambda: cls.yesterday(now=now, timezone_name=timezone_name),
            "this week": lambda: cls.this_week(now=now, timezone_name=timezone_name),
            "this month": lambda: cls.this_month(now=now, timezone_name=timezone_name),
            "last week": lambda: cls.last_week(now=now, timezone_name=timezone_name),
            "past week": lambda: cls.last_week(now=now, timezone_name=timezone_name),
            "last 2 weeks": lambda: cls.last_two_weeks(now=now, timezone_name=timezone_name),
            "last two weeks": lambda: cls.last_two_weeks(now=now, timezone_name=timezone_name),
            "last 4 weeks": lambda: cls.last_four_weeks(now=now, timezone_name=timezone_name),
            "last four weeks": lambda: cls.last_four_weeks(now=now, timezone_name=timezone_name),
            "preceding four weeks": lambda: cls.last_four_weeks(now=now, timezone_name=timezone_name),
            "previous calendar month": lambda: cls.last_month(
                now=now, timezone_name=timezone_name
            ),
            "previous month": lambda: cls.last_month(
                now=now, timezone_name=timezone_name
            ),
            "previous week": lambda: cls.last_week(now=now, timezone_name=timezone_name),
            "last month": lambda: cls.last_month(
                now=now,
                timezone_name=timezone_name,
            ),
            "past month": lambda: cls.rolling_days(30, now=now),
            "past 30 days": lambda: cls.rolling_days(30, now=now),
            "last 30 days": lambda: cls.rolling_days(30, now=now),
            "latest": lambda: cls.latest(now=now, timezone_name=timezone_name),
            "current": lambda: cls.latest(now=now, timezone_name=timezone_name),
            "right now": lambda: cls.latest(now=now, timezone_name=timezone_name),
            "bugün": lambda: cls._with_display_name(cls.today(now=now, timezone_name=timezone_name), "bugün"),
            "dün": lambda: cls._with_display_name(cls.yesterday(now=now, timezone_name=timezone_name), "dün"),
            "bu hafta": lambda: cls._with_display_name(cls.this_week(now=now, timezone_name=timezone_name), "bu hafta"),
            "geçen hafta": lambda: cls._with_display_name(cls.last_week(now=now, timezone_name=timezone_name), "geçen hafta"),
            "son hafta": lambda: cls._with_display_name(cls.last_week(now=now, timezone_name=timezone_name), "son hafta"),
            "son 2 hafta": lambda: cls._with_display_name(cls.last_two_weeks(now=now, timezone_name=timezone_name), "son 2 hafta"),
            "son iki hafta": lambda: cls._with_display_name(cls.last_two_weeks(now=now, timezone_name=timezone_name), "son iki hafta"),
            "son 4 hafta": lambda: cls._with_display_name(cls.last_four_weeks(now=now, timezone_name=timezone_name), "son dört hafta"),
            "son dört hafta": lambda: cls._with_display_name(cls.last_four_weeks(now=now, timezone_name=timezone_name), "son dört hafta"),
            "bu ay": lambda: cls._with_display_name(cls.this_month(now=now, timezone_name=timezone_name), "bu ay"),
            "geçen ay": lambda: cls._with_display_name(
                cls.last_month(now=now, timezone_name=timezone_name), "geçen ay"
            ),
            "son ay": lambda: cls._with_display_name(cls.rolling_days(30, now=now), "son ay"),
            "son 30 gün": lambda: cls._with_display_name(cls.rolling_days(30, now=now), "son 30 gün"),
            "son otuz gün": lambda: cls._with_display_name(cls.rolling_days(30, now=now), "son otuz gün"),
            "şimdi": lambda: cls._with_display_name(cls.latest(now=now, timezone_name=timezone_name), "en güncel"),
            "şu anda": lambda: cls._with_display_name(cls.latest(now=now, timezone_name=timezone_name), "en güncel"),
            "en güncel": lambda: cls._with_display_name(cls.latest(now=now, timezone_name=timezone_name), "en güncel"),
        }

        factory = mapping.get(normalized)
        if factory is not None:
            return factory()

        named_month = re.fullmatch(
            r"(" + "|".join(month.lower() for month in calendar.month_name[1:]) + r")\s+(\d{4})",
            normalized,
        )
        if named_month:
            month_name, year_text = named_month.groups()
            month = list(calendar.month_name).index(month_name.title())
            return cls._calendar_month(
                year=int(year_text),
                month=month,
                timezone_name=timezone_name,
                now=now,
            )

        turkish_months = {
            "ocak": 1, "şubat": 2, "mart": 3, "nisan": 4,
            "mayıs": 5, "mayis": 5, "haziran": 6, "temmuz": 7, "ağustos": 8,
            "eylül": 9, "eylul": 9, "ekim": 10, "kasım": 11, "kasim": 11,
            "aralık": 12, "aralik": 12, "subat": 2, "agustos": 8,
        }
        turkish_month = re.fullmatch(
            r"(" + "|".join(turkish_months) + r")\s+(\d{4})",
            normalized,
        )
        if turkish_month:
            month_name, year_text = turkish_month.groups()
            period = cls._calendar_month(
                year=int(year_text),
                month=turkish_months[month_name],
                timezone_name=timezone_name,
                now=now,
            )
            return cls._with_display_name(period, f"{month_name} {year_text}")

        month_numbers = {
            **{name.lower(): number for number, name in enumerate(calendar.month_name) if name},
            **turkish_months,
        }
        month_range = re.fullmatch(
            r"(" + "|".join(month_numbers) + r")(?:\s+(\d{4}))?\s*"
            r"(?:to|through|and|ile|-)\s*(" + "|".join(month_numbers) + r")\s+(\d{4})",
            normalized,
        )
        if month_range:
            first_name, first_year_text, last_name, last_year_text = month_range.groups()
            first_year = int(first_year_text or last_year_text)
            last_year = int(last_year_text)
            first = cls._calendar_month(
                year=first_year,
                month=month_numbers[first_name],
                timezone_name=timezone_name,
                now=now,
            )
            last = cls._calendar_month(
                year=last_year,
                month=month_numbers[last_name],
                timezone_name=timezone_name,
                now=now,
            )
            if last.start < first.start:
                raise ValueError("The end month must not precede the start month")
            first_label = first_name.title() + (f" {first_year}" if first_year != last_year else "")
            return cls(
                start=first.start,
                end=last.end,
                display_name=f"{first_label}–{last_name.title()} {last_year}",
            )

        iso_range = re.fullmatch(
            r"(?:from\s+)?(\d{4}-\d{2}-\d{2})\s+(?:to|through|until)\s+(\d{4}-\d{2}-\d{2})",
            normalized,
        )
        if iso_range:
            return cls._explicit_date_range(
                iso_range.group(1),
                iso_range.group(2),
                timezone_name=timezone_name,
                now=now,
            )

        turkish_iso_range = re.fullmatch(
            r"(?:.*?)?(\d{4}-\d{2}-\d{2})\s+(?:ile|ila)\s+(\d{4}-\d{2}-\d{2})(?:\s+arası)?",
            normalized,
        )
        if turkish_iso_range:
            period = cls._explicit_date_range(
                turkish_iso_range.group(1),
                turkish_iso_range.group(2),
                timezone_name=timezone_name,
                now=now,
            )
            return cls._with_display_name(
                period,
                f"{turkish_iso_range.group(1)} ile {turkish_iso_range.group(2)} arası",
            )

        raise ValueError(
            "Unsupported time period. Try today, yesterday, last week, "
            "last month, past 30 days, a named month such as July 2026, "
            "or an ISO range such as 2026-07-01 to 2026-07-31."
        )

    @classmethod
    def _with_display_name(cls, period: TimePeriod, display_name: str) -> TimePeriod:
        """Return an equivalent period with a localized display label."""
        return cls(start=period.start, end=period.end, display_name=display_name)

    @staticmethod
    def _resolve_timezone(timezone_name: str):
        """Resolve an IANA site timezone with a clear validation error."""
        try:
            if not timezone_name:
                raise ValueError("Organization timezone is not verified")
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError as exc:
            raise ValueError(f"Unknown site timezone: {timezone_name}") from exc

    @classmethod
    def _calendar_month(
        cls,
        *,
        year: int,
        month: int,
        timezone_name: str,
        now: datetime | None,
    ) -> TimePeriod:
        tz = cls._resolve_timezone(timezone_name)
        start = datetime(year, month, 1, tzinfo=tz)
        if month == 12:
            end = datetime(year + 1, 1, 1, tzinfo=tz)
        else:
            end = datetime(year, month + 1, 1, tzinfo=tz)
        cls._reject_future(start, now=now, tz=tz)
        return cls(
            start=start.astimezone(timezone.utc),
            end=end.astimezone(timezone.utc),
            display_name=f"{calendar.month_name[month]} {year}",
        )

    @classmethod
    def _explicit_date_range(
        cls,
        start_text: str,
        end_text: str,
        *,
        timezone_name: str,
        now: datetime | None,
    ) -> TimePeriod:
        tz = cls._resolve_timezone(timezone_name)
        start = datetime.fromisoformat(start_text).replace(tzinfo=tz)
        end_day = datetime.fromisoformat(end_text).replace(tzinfo=tz)
        cls._reject_future(start, now=now, tz=tz)
        cls._reject_future(end_day, now=now, tz=tz)
        end = end_day + timedelta(days=1)
        return cls(
            start=start.astimezone(timezone.utc),
            end=end.astimezone(timezone.utc),
            display_name=f"{start_text} to {end_text}",
        )

    @staticmethod
    def _reject_future(value: datetime, *, now: datetime | None, tz) -> None:
        reference = now or datetime.now(tz=tz)
        if reference.tzinfo is None:
            reference = reference.replace(tzinfo=tz)
        if value.date() > reference.astimezone(tz).date():
            raise ValueError("Future time periods are not available")
    
    @property
    def duration_days(self) -> float:
        """Duration of the period in days."""
        return (self.end - self.start).total_seconds() / 86400


@dataclass(frozen=True)
class DataPoint:
    """
    Single data point in a time series.
    
    Attributes:
        timestamp: When this measurement was taken
        value: The measured value
        unit: Unit of measurement
    """
    
    timestamp: datetime
    value: float
    unit: str = ""
    
    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
        }


@dataclass(frozen=True)
class ScenarioParameter:
    """
    A single parameter change in a what-if scenario.
    
    Attributes:
        name: Parameter name (e.g., "temperature", "speed")
        baseline_value: Current value
        proposed_value: Simulated value
        unit: Unit of measurement
    """
    
    name: str
    baseline_value: float
    proposed_value: float
    unit: str = ""
    
    @property
    def delta(self) -> float:
        """Change from baseline to proposed."""
        return self.proposed_value - self.baseline_value
    
    @property
    def delta_percent(self) -> float:
        """Percentage change from baseline."""
        if self.baseline_value == 0:
            return 0.0
        return (self.delta / self.baseline_value) * 100


@dataclass(frozen=True)
class WhatIfScenario:
    """
    Definition of a what-if simulation scenario.
    
    Attributes:
        name: Scenario identifier
        asset_id: Target asset/machine
        parameters: List of parameter changes to simulate
        target_metric: The metric to predict impact on
    """
    
    name: str
    asset_id: str
    parameters: tuple[ScenarioParameter, ...]
    target_metric: CanonicalMetric
    
    def __init__(
        self,
        name: str,
        asset_id: str,
        parameters: list[ScenarioParameter] | tuple[ScenarioParameter, ...],
        target_metric: CanonicalMetric,
    ):
        """Initialize with parameter list converted to tuple for immutability."""
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "parameters", tuple(parameters))
        object.__setattr__(self, "target_metric", target_metric)


@dataclass(frozen=True)
class Anomaly:
    """
    Detected anomaly in manufacturing data.
    
    Attributes:
        timestamp: When the anomaly occurred
        metric: Which metric showed the anomaly
        expected_value: What was expected
        actual_value: What was observed
        deviation: Standard deviations from expected
        anomaly_type: Direction of anomaly ("spike", "dip", or "")
        description: Human-readable description
    """
    
    timestamp: datetime
    metric: CanonicalMetric
    expected_value: float
    actual_value: float
    deviation: float
    anomaly_type: str = ""
    description: str = ""
    
    @property
    def severity(self) -> Literal["low", "medium", "high", "critical"]:
        """Categorize severity based on deviation magnitude."""
        abs_dev = abs(self.deviation)
        if abs_dev < 2:
            return "low"
        elif abs_dev < 3:
            return "medium"
        elif abs_dev < 4:
            return "high"
        return "critical"


# Emission factor models extracted to emission_factors.py (file-size compliance).
# Re-exported here for backward compatibility.
from skill.domain.emission_factors import (  # noqa: F401, E402
    DEFAULT_EMISSION_FACTORS,
    EmissionFactor,
)
