from datetime import datetime, timedelta, timezone

from skill.domain.models import TimePeriod
from skill.domain.reneryo_models import (
    LocalizedText,
    MdspFinding,
    MdspFindingList,
    ReneryoMeter,
    ReneryoMetric,
    ReneryoRegression,
)
from skill.services.futuregen_responses import (
    finding_inventory_headline,
    meter_inventory_headline,
    metric_detail_headline,
    metric_inventory_headline,
    reneryo_capabilities_headline,
    regression_detail_headline,
    regression_inventory_headline,
)


def _regression(driver: str, period: str, r_squared: float) -> ReneryoRegression:
    return ReneryoRegression(
        regression_id=f"{driver}-{period}",
        regression_type="advanced",
        driver_names=(driver,),
        slice_names=("Future Gen Ana Tesis",),
        period=period,
        r_squared=r_squared,
        rmse=10.0,
        primary=False,
        train_start=datetime(2024, 1, 1, tzinfo=timezone.utc),
        train_end=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


def test_regression_inventory_uses_available_metadata_instead_of_count_only():
    rows = [
        _regression("Tesis Toplam Üretim Miktarı", "DAILY", 0.72),
        _regression("Heating degree days", "MONTHLY", 0.21),
        _regression("Cooling degree days", "MONTHLY", 0.18),
    ]

    answer = regression_inventory_headline(rows, "en-US")

    assert "3 saved regression models: 3 advanced" in answer
    assert "daily and monthly" in answer
    assert "Tesis Toplam Üretim Miktarı" in answer
    assert "R-squared ranges from 0.180 to 0.720" in answer
    assert "None is marked as the primary model" in answer


def test_futuregen_capabilities_are_bilingual_and_domain_scoped():
    english = reneryo_capabilities_headline("en-US")
    turkish = reneryo_capabilities_headline("tr-TR")

    assert "active MDSP findings" in english
    assert "English and Turkish" in english
    assert "etkin MDSP bulgularını" in turkish
    assert "Türkçe ve İngilizce" in turkish


def test_regression_inventory_is_natural_in_turkish():
    rows = [
        _regression("Tesis Toplam Üretim Miktarı", "DAILY", 0.72),
        _regression("Isıtma derece gün", "MONTHLY", 0.21),
    ]

    answer = regression_inventory_headline(rows, "tr-TR")

    assert "2 kayıtlı regresyon modeli" in answer
    assert "günlük ve aylık" in answer
    assert "Hiçbiri birincil model olarak işaretli değil" in answer


def test_regression_detail_uses_only_available_model_metadata():
    row = _regression("Tesis Toplam Üretim Miktarı", "DAILY", 0.72)

    answer = regression_detail_headline(row, "en-US")

    assert "advanced regression model" in answer
    assert "daily period" in answer
    assert "Tesis Toplam Üretim Miktarı" in answer
    assert "R-squared is 0.720" in answer
    assert "RMSE is 10.000" in answer


def test_regression_detail_localizes_model_type_in_turkish():
    answer = regression_detail_headline(
        _regression("Tesis Toplam Üretim Miktarı", "DAILY", 0.72), "tr-TR"
    )

    assert "gelişmiş regresyon modeli" in answer
    assert "advanced" not in answer


def test_meter_inventory_qualifies_zero_default_period():
    period = TimePeriod(
        datetime.now(timezone.utc) - timedelta(days=30),
        datetime.now(timezone.utc),
        "last 30 days",
    )
    rows = [
        ReneryoMeter(
            meter_id="meter-1",
            name="Future Gen Ana Elektrik Sayacı",
            energy_resource="ELECTRICITY",
            consumption=0.0,
            metric_id="metric-1",
            metric_name="Tesis Toplam Elektrik Tüketimi",
            slice_names=("Future Gen Ana Tesis",),
        )
    ]

    answer = meter_inventory_headline(rows, period, "en-US")

    assert "Future Gen Ana Elektrik Sayacı" in answer
    assert "linked to Tesis Toplam Elektrik Tüketimi" in answer
    assert "0.00" in answer
    assert "does not mean" in answer


def test_meter_inventory_localizes_latest_available_period_in_turkish():
    period = TimePeriod(
        datetime.now(timezone.utc) - timedelta(days=30),
        datetime.now(timezone.utc),
        "latest available",
    )
    rows = [
        ReneryoMeter(
            meter_id="meter-1",
            name="Future Gen Ana Elektrik Sayacı",
            energy_resource="ELECTRICITY",
            consumption=12.5,
            metric_id="metric-1",
            metric_name="Tesis Toplam Elektrik Tüketimi",
            slice_names=("Future Gen Ana Tesis",),
        )
    ]

    answer = meter_inventory_headline(rows, period, "tr-TR")

    assert "mevcut en güncel dönemi" in answer
    assert "latest available" not in answer


def test_metric_inventory_names_domains_and_watermark():
    rows = [
        ReneryoMetric(
            "metric-1",
            "Tesis Toplam Elektrik Tüketimi",
            "COUNTER",
            "ENERGY",
            last_value_at=datetime(2026, 6, 30, 21, 0, tzinfo=timezone.utc),
        ),
        ReneryoMetric(
            "metric-2",
            "Temperature - Open Weather",
            "GAUGE",
            "TEMPERATURE",
            last_value_at=datetime(2026, 9, 17, 11, 21, tzinfo=timezone.utc),
        ),
    ]

    answer = metric_inventory_headline(rows, "en-US")

    assert "2 metrics" in answer
    assert "Tesis Toplam Elektrik Tüketimi" in answer
    assert "Temperature - Open Weather" in answer
    assert "17 September 2026 11:21 UTC" in answer


def test_metric_detail_uses_context_selected_reneryo_metadata():
    metric = ReneryoMetric(
        "metric-1",
        "Cooling degree days - Open Weather",
        "GAUGE",
        "TEMPERATURE",
        last_value=5.15,
        last_value_at=datetime(2026, 9, 17, 11, 21, tzinfo=timezone.utc),
    )

    answer = metric_detail_headline(metric, "en-US")

    assert "Cooling degree days - Open Weather" in answer
    assert "instantaneous measurement" in answer
    assert "temperature" in answer
    assert "5.15" in answer
    assert "17 September 2026 11:21 UTC" in answer


def test_finding_inventory_summarizes_severity_and_domain():
    now = datetime.now(timezone.utc)

    def finding(number: int, severity: str, domain: str) -> MdspFinding:
        return MdspFinding(
            finding_id=f"finding-{number}",
            status="ACTIVE",
            severity=severity,
            domain=domain,
            entity_type="TEST",
            entity_id=f"entity-{number}",
            title=LocalizedText(en="Finding", tr="Bulgu"),
            summary=LocalizedText(en="Summary", tr="Özet"),
            evidence={},
            assumptions=(),
            evaluation_start=now,
            evaluation_end=now,
            source_watermark=now,
            deep_link=None,
            provisional=True,
        )

    findings = tuple(
        [finding(index, "MEDIUM", "METRICS") for index in range(4)]
        + [finding(index + 4, "LOW", "METRICS") for index in range(2)]
        + [finding(index + 6, "LOW", "REGRESSION") for index in range(4)]
    )
    result = MdspFindingList(findings, 10, 0, {"MEDIUM": 4, "LOW": 6})

    answer = finding_inventory_headline(result, "en-US")

    assert "10 active findings" in answer
    assert "0 high, 4 medium and 6 low" in answer
    assert "6 concern metrics" in answer
    assert "4 concern regression analysis" in answer
