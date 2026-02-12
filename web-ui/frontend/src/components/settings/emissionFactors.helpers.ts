import type {
  EmissionFactorPresetResponse,
  EmissionFactorRequest,
  EmissionFactorResponse,
  EnergySource,
} from "../../api/types";

export type FactorErrors = Partial<Record<keyof EmissionFactorRequest, string>>;

export const ENERGY_SOURCES: EnergySource[] = ["electricity", "gas", "water"];
export const FALLBACK_PRESET_COUNTRY = "TR";

export const EMPTY_FORM: EmissionFactorRequest = {
  energy_source: "electricity",
  factor: 0,
  country: "",
  source: "",
  year: new Date().getFullYear(),
};

export function isEnergySource(value: string): value is EnergySource {
  return ENERGY_SOURCES.includes(value as EnergySource);
}

export function formatEnergySource(source: string): string {
  if (source === "electricity") return "Electricity";
  if (source === "gas") return "Gas";
  if (source === "water") return "Water";
  return source;
}

export function validateForm(form: EmissionFactorRequest): FactorErrors {
  const errors: FactorErrors = {};
  if (!isEnergySource(form.energy_source)) {
    errors.energy_source = "Invalid energy source.";
  }
  if (!Number.isFinite(form.factor) || form.factor <= 0) {
    errors.factor = "Factor must be greater than 0.";
  }
  return errors;
}

export function computeEffectiveFactors(
  factors: EmissionFactorResponse[],
  presets: EmissionFactorPresetResponse[],
): Array<{
  energy_source: EnergySource;
  factor: number | undefined;
  country: string | undefined;
  source: string | undefined;
  year: number | undefined;
  origin: "Custom" | "Fallback" | "Unavailable";
}> {
  const stored = new Map(factors.map((item) => [item.energy_source, item]));
  const fallback = new Map(
    presets
      .filter((item) => item.country === FALLBACK_PRESET_COUNTRY)
      .map((item) => [item.energy_source, item]),
  );

  return ENERGY_SOURCES.map((source) => {
    const active = stored.get(source) ?? fallback.get(source);
    return {
      energy_source: source,
      factor: active?.factor,
      country: active?.country,
      source: active?.source,
      year: active?.year,
      origin: stored.has(source) ? "Custom" : active ? "Fallback" : "Unavailable",
    };
  });
}
