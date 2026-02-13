import { useCallback, useEffect, useMemo, useState } from "react";

import {
  createEmissionFactor,
  deleteEmissionFactor,
  listEmissionFactorPresets,
  listEmissionFactors,
  toFriendlyErrorMessage,
} from "../../api/client";
import type {
  EmissionFactorPresetResponse,
  EmissionFactorRequest,
  EmissionFactorResponse,
  EnergySource,
} from "../../api/types";
import ErrorMessage from "../common/ErrorMessage";
import LoadingSpinner from "../common/LoadingSpinner";
import { useTheme } from "../common/ThemeProvider";
import EmissionFactorsConfiguredList from "./EmissionFactorsConfiguredList";
import {
  computeEffectiveFactors,
  EMPTY_FORM,
  ENERGY_SOURCES,
  FALLBACK_PRESET_COUNTRY,
  type FactorErrors,
  formatEnergySource,
  isEnergySource,
  validateForm,
} from "./emissionFactors.helpers";

type EmissionFactorsSectionProps = {
  onNotify: (type: "success" | "error", message: string) => void;
};

export default function EmissionFactorsSection({ onNotify }: EmissionFactorsSectionProps) {
  const { isDark } = useTheme();
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [deletingSource, setDeletingSource] = useState<string | null>(null);
  const [factors, setFactors] = useState<EmissionFactorResponse[]>([]);
  const [presets, setPresets] = useState<EmissionFactorPresetResponse[]>([]);
  const [selectedCountry, setSelectedCountry] = useState(FALLBACK_PRESET_COUNTRY);
  const [showAddForm, setShowAddForm] = useState(false);
  const [form, setForm] = useState<EmissionFactorRequest>(EMPTY_FORM);
  const [errors, setErrors] = useState<FactorErrors>({});
  const [inlineError, setInlineError] = useState("");

  const loadData = useCallback(async () => {
    setLoading(true);
    setInlineError("");
    try {
      const [factorResponse, presetResponse] = await Promise.all([
        listEmissionFactors(),
        listEmissionFactorPresets(),
      ]);
      setFactors(factorResponse.factors);
      setPresets(presetResponse);
    } catch (error: unknown) {
      const message = toFriendlyErrorMessage(error);
      setInlineError(message);
      onNotify("error", message);
    } finally {
      setLoading(false);
    }
  }, [onNotify]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const countries = useMemo(
    () => Array.from(new Set(presets.map((item) => item.country))).sort(),
    [presets],
  );

  useEffect(() => {
    if (countries.length > 0 && !countries.includes(selectedCountry)) {
      setSelectedCountry(countries[0]);
    }
  }, [countries, selectedCountry]);

  const selectedPresetEntries = useMemo(
    () => presets.filter((item) => item.country === selectedCountry),
    [presets, selectedCountry],
  );

  const effectiveFactors = useMemo(
    () => computeEffectiveFactors(factors, presets),
    [factors, presets],
  );

  const updateForm = useCallback(<K extends keyof EmissionFactorRequest>(key: K, value: EmissionFactorRequest[K]) => {
    setForm((prev) => ({ ...prev, [key]: value }));
    setErrors((prev) => {
      if (!prev[key]) return prev;
      const next = { ...prev };
      delete next[key];
      return next;
    });
  }, []);

  const handleSave = useCallback(async () => {
    const validationErrors = validateForm(form);
    setErrors(validationErrors);
    if (Object.keys(validationErrors).length > 0) {
      onNotify("error", "Please fix validation errors before saving.");
      return;
    }

    setSaving(true);
    try {
      await createEmissionFactor(form);
      onNotify("success", "Emission factor saved.");
      setShowAddForm(false);
      setForm(EMPTY_FORM);
      setErrors({});
      await loadData();
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }, [form, loadData, onNotify]);

  const handleDelete = useCallback(
    async (energySource: string) => {
      setDeletingSource(energySource);
      try {
        await deleteEmissionFactor(energySource);
        onNotify("success", `${formatEnergySource(energySource)} factor deleted.`);
        await loadData();
      } catch (error: unknown) {
        onNotify("error", toFriendlyErrorMessage(error));
      } finally {
        setDeletingSource(null);
      }
    },
    [loadData, onNotify],
  );

  const applyPreset = useCallback(async () => {
    if (selectedPresetEntries.length === 0) {
      onNotify("error", "No preset entries found for selected country.");
      return;
    }

    setSaving(true);
    try {
      const tasks = selectedPresetEntries
        .filter((item) => isEnergySource(item.energy_source))
        .map((item) =>
          createEmissionFactor({
            energy_source: item.energy_source as EnergySource,
            factor: item.factor,
            country: item.country,
            source: item.source,
            year: item.year,
          }),
        );
      await Promise.all(tasks);
      onNotify("success", `${selectedCountry} preset applied.`);
      await loadData();
    } catch (error: unknown) {
      onNotify("error", toFriendlyErrorMessage(error));
    } finally {
      setSaving(false);
    }
  }, [loadData, onNotify, selectedCountry, selectedPresetEntries]);

  return (
    <section className="space-y-3">
      <div className="brand-surface rounded-xl p-4">
        <p className="m-0 text-sm text-slate-700 dark:text-slate-300">
          Emission factors convert energy consumption (kWh) to CO2-equivalent (kg CO2-eq). Default
          factor for Turkiye electricity: 0.48 kg CO2/kWh.
        </p>
      </div>

      {inlineError && <ErrorMessage title="Emission factors error" message={inlineError} onRetry={() => void loadData()} />}

      {loading ? (
        <div className="rounded-lg border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900 opacity-50">
          <LoadingSpinner label="Loading emission factors..." size="sm" />
        </div>
      ) : (
        <>
          <div className="brand-surface reveal-in rounded-xl p-4">
            <div className="grid gap-3 md:grid-cols-[minmax(0,240px)_auto] md:items-end">
              <label className="block">
                <span className="mb-1 block text-xs font-semibold uppercase text-slate-500">Country Preset</span>
                <select
                  value={selectedCountry}
                  onChange={(event) => setSelectedCountry(event.target.value)}
                  className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                >
                  {countries.length === 0 ? <option value="">No presets available</option> : null}
                  {countries.map((country) => (
                    <option key={country} value={country}>
                      {country}
                    </option>
                  ))}
                </select>
              </label>
              <button
                type="button"
                onClick={() => void applyPreset()}
                disabled={saving || !selectedCountry}
                className="btn-brand-primary rounded-lg px-3 py-2 text-xs font-semibold md:w-fit"
              >
                {saving ? "Applying..." : `Apply ${selectedCountry || "Preset"} Preset`}
              </button>
            </div>
          </div>

          <div className="brand-surface rounded-xl p-4">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h4 className="m-0 text-sm font-semibold text-slate-900">Configured Factors</h4>
              <button
                type="button"
                onClick={() => setShowAddForm((prev) => !prev)}
                className={`rounded-lg border px-3 py-1.5 text-xs font-semibold ${
                  isDark
                    ? "border-slate-500 bg-slate-700 text-slate-100 hover:bg-slate-600"
                    : "border-slate-300 bg-white text-slate-700"
                }`}
              >
                {showAddForm ? "Cancel" : "Add Custom Factor"}
              </button>
            </div>

            {showAddForm ? (
              <div className="mb-4 grid gap-3 md:grid-cols-5">
                <select value={form.energy_source} onChange={(event) => updateForm("energy_source", event.target.value as EnergySource)} className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100">
                  {ENERGY_SOURCES.map((source) => (
                    <option key={source} value={source}>{formatEnergySource(source)}</option>
                  ))}
                </select>
                <input type="number" min="0" step="0.0001" value={form.factor} onChange={(event) => updateForm("factor", Number(event.target.value))} placeholder="Factor" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100" />
                <input type="text" value={form.country} onChange={(event) => updateForm("country", event.target.value)} placeholder="Country" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100" />
                <input type="text" value={form.source} onChange={(event) => updateForm("source", event.target.value)} placeholder="Source" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100" />
                <input type="number" min="2000" max="2030" value={form.year} onChange={(event) => updateForm("year", Number(event.target.value))} placeholder="Year" className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100" />
                <div className="md:col-span-5 flex items-center justify-between gap-3">
                  <p className="m-0 text-xs text-rose-600 dark:text-rose-300">{errors.factor ?? errors.energy_source ?? " "}</p>
                  <button type="button" onClick={() => void handleSave()} disabled={saving} className="btn-brand-primary rounded-lg px-3 py-2 text-xs font-semibold">
                    {saving ? "Saving..." : "Save Factor"}
                  </button>
                </div>
              </div>
            ) : null}

            <EmissionFactorsConfiguredList
              factors={factors}
              deletingSource={deletingSource}
              isDark={isDark}
              onDelete={(energySource) => void handleDelete(energySource)}
            />
          </div>

          <div className="brand-surface rounded-xl p-4">
            <h4 className="m-0 mb-2 text-sm font-semibold text-slate-900">Current Effective Factors</h4>
            <div className="grid gap-2 md:grid-cols-3">
              {effectiveFactors.map((item) => (
                <div key={item.energy_source} className="brand-surface-muted rounded-lg p-3">
                  <p className="m-0 text-xs font-semibold uppercase tracking-wide text-slate-500">{formatEnergySource(item.energy_source)}</p>
                  <p className="m-0 mt-1 text-sm font-semibold text-slate-900">{typeof item.factor === "number" ? item.factor.toFixed(4) : "N/A"}</p>
                  <p className="m-0 mt-1 text-xs text-slate-600">{item.origin} {item.country ? `(${item.country})` : ""}{item.year ? ` • ${item.year}` : ""}</p>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
