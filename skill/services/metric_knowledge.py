"""Canonical deterministic manufacturing metric knowledge registry."""

from __future__ import annotations

from dataclasses import dataclass

from skill.domain.models import CanonicalMetric


@dataclass(frozen=True)
class MetricKnowledge:
    definition: str
    formula: str
    direction: str
    data_requirements: str


_DEFAULT = MetricKnowledge(
    definition="A configured manufacturing performance measure.",
    formula="The calculation is defined by the connected source mapping.",
    direction="No performance direction is assumed without a configured objective.",
    data_requirements="A mapped source value, asset, observation time, and unit.",
)

METRIC_KNOWLEDGE: dict[CanonicalMetric, MetricKnowledge] = {
    CanonicalMetric.OEE: MetricKnowledge(
        "Overall equipment effectiveness combines availability, performance, and quality.",
        "OEE = availability × performance × quality × 100.",
        "Higher is normally desirable, but AVAROS judges it only against a configured site objective.",
        "Run time, planned production time, ideal cycle time, total count, and good count.",
    ),
    CanonicalMetric.ENERGY_PER_UNIT: MetricKnowledge(
        "Energy per unit is the energy used for each produced unit.",
        "Energy per unit = total energy consumed ÷ units produced.",
        "Lower usually means less energy intensity; site objectives control judgments.",
        "Aligned energy consumption and production count for the same asset and period.",
    ),
    CanonicalMetric.ENERGY_TOTAL: MetricKnowledge(
        "Total energy is all energy consumed over the requested period.",
        "Total energy = sum of period energy observations.",
        "Direction alone is not good or bad because production volume also matters.",
        "Complete period energy observations in a consistent unit.",
    ),
    CanonicalMetric.PEAK_DEMAND: MetricKnowledge(
        "Peak demand is the highest power demand observed during the period.",
        "Peak demand = maximum period demand observation.",
        "Lower peaks may reduce capacity and tariff exposure, subject to site objectives.",
        "Time-stamped power-demand observations covering the requested period.",
    ),
    CanonicalMetric.SCRAP_RATE: MetricKnowledge(
        "Scrap rate is the share of production that cannot be recovered as good output.",
        "Scrap rate = scrapped quantity ÷ total produced quantity × 100.",
        "Lower is normally desirable; AVAROS requires a configured objective to rate it.",
        "Scrap quantity and total production for the same asset and period.",
    ),
    CanonicalMetric.REWORK_RATE: MetricKnowledge(
        "Rework rate is the share of output requiring additional processing.",
        "Rework rate = reworked quantity ÷ total produced quantity × 100.",
        "Lower is normally desirable, subject to a configured objective.",
        "Reworked and total quantities for the same scope and period.",
    ),
    CanonicalMetric.MATERIAL_EFFICIENCY: MetricKnowledge(
        "Material efficiency is the share of input material represented in useful output.",
        "Material efficiency = useful output material ÷ input material × 100.",
        "Higher is normally desirable, subject to a configured objective.",
        "Input material and useful output material for an aligned period.",
    ),
    CanonicalMetric.THROUGHPUT: MetricKnowledge(
        "Throughput is the quantity produced per unit of time.",
        "Throughput = produced quantity ÷ operating time.",
        "The desired direction depends on quality, demand, and the configured objective.",
        "Production count and aligned operating duration.",
    ),
    CanonicalMetric.CYCLE_TIME: MetricKnowledge(
        "Cycle time is the elapsed production time per completed unit.",
        "Cycle time = production elapsed time ÷ completed units.",
        "Lower may indicate faster production, but quality and objectives must also be considered.",
        "Aligned elapsed time and completed-unit count.",
    ),
    CanonicalMetric.CHANGEOVER_TIME: MetricKnowledge(
        "Changeover time is the elapsed time required to switch production setup.",
        "Changeover time = ready-for-next-run time minus prior-run completion time.",
        "Lower is normally desirable, subject to safe and validated procedures.",
        "Time-stamped prior-run completion and next-run readiness events.",
    ),
    CanonicalMetric.CO2_TOTAL: MetricKnowledge(
        "Total carbon emissions are the period greenhouse-gas emissions expressed as CO2 equivalent.",
        "Total CO2e = sum of activity data × applicable emission factors.",
        "Lower absolute emissions may be desirable, but production volume and objectives matter.",
        "Complete activity data, source-specific emission factors, and period coverage.",
    ),
    CanonicalMetric.CO2_PER_UNIT: MetricKnowledge(
        "Carbon per unit is greenhouse-gas emissions allocated to each produced unit.",
        "CO2e per unit = total CO2e ÷ units produced.",
        "Lower is normally desirable, subject to a configured objective.",
        "Aligned total CO2e and production count.",
    ),
}


def get_metric_knowledge(metric: CanonicalMetric) -> MetricKnowledge:
    return METRIC_KNOWLEDGE.get(metric, _DEFAULT)
