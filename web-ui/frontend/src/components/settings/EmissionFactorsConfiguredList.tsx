import type { EmissionFactorResponse } from "../../api/types";
import { formatEnergySource } from "./emissionFactors.helpers";

type EmissionFactorsConfiguredListProps = {
  factors: EmissionFactorResponse[];
  deletingSource: string | null;
  isDark: boolean;
  readOnly?: boolean;
  onDelete: (energySource: string) => void;
};

export default function EmissionFactorsConfiguredList({
  factors,
  deletingSource,
  isDark,
  readOnly = false,
  onDelete,
}: EmissionFactorsConfiguredListProps) {
  if (factors.length === 0) {
    return (
      <div className="rounded-lg border border-slate-200 px-3 py-4 text-sm text-slate-500 dark:border-slate-700">
        No custom emission factors configured.
      </div>
    );
  }

  const deleteButtonClass = `rounded border px-2 py-1 text-xs font-semibold ${
    isDark
      ? "border-rose-400 bg-rose-950/60 text-rose-200"
      : "border-rose-300 bg-rose-50 text-rose-700"
  }`;

  return (
    <>
      <div className="space-y-2 md:hidden">
        {factors.map((factor) => (
          <article
            key={factor.energy_source}
            className="rounded-lg border border-slate-200 p-3 dark:border-slate-700"
          >
            <div className="grid grid-cols-2 gap-2 text-xs">
              <span className="text-slate-500">Energy</span>
              <span className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {formatEnergySource(factor.energy_source)}
              </span>
              <span className="text-slate-500">Factor</span>
              <span className="text-right font-semibold text-slate-900 dark:text-slate-100">
                {factor.factor.toFixed(4)}
              </span>
              <span className="text-slate-500">Country</span>
              <span className="text-right text-slate-700 dark:text-slate-200">{factor.country || "-"}</span>
              <span className="text-slate-500">Source</span>
              <span className="text-right text-slate-700 dark:text-slate-200">{factor.source || "-"}</span>
              <span className="text-slate-500">Year</span>
              <span className="text-right text-slate-700 dark:text-slate-200">{factor.year}</span>
            </div>
            <button
              type="button"
              onClick={() => onDelete(factor.energy_source)}
              className={`${deleteButtonClass} mt-3 w-full py-1.5`}
              disabled={readOnly || deletingSource === factor.energy_source}
            >
              {deletingSource === factor.energy_source ? "Removing..." : "Delete"}
            </button>
          </article>
        ))}
      </div>

      <div className="hidden overflow-x-auto rounded-lg border border-slate-200 dark:border-slate-700 md:block">
        <table className="min-w-full border-collapse text-sm">
          <thead className="bg-slate-100 dark:bg-slate-800">
            <tr>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Energy Source</th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Factor (kg CO2/kWh)</th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Country</th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Source</th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Year</th>
              <th className="px-3 py-2 text-left text-xs font-semibold uppercase text-slate-600">Action</th>
            </tr>
          </thead>
          <tbody>
            {factors.map((factor) => (
              <tr key={factor.energy_source} className="border-t border-slate-200 dark:border-slate-700">
                <td className="px-3 py-3">{formatEnergySource(factor.energy_source)}</td>
                <td className="px-3 py-3">{factor.factor.toFixed(4)}</td>
                <td className="px-3 py-3">{factor.country || "-"}</td>
                <td className="px-3 py-3">{factor.source || "-"}</td>
                <td className="px-3 py-3">{factor.year}</td>
                <td className="px-3 py-3">
                  <button
                    type="button"
                    onClick={() => onDelete(factor.energy_source)}
                    className={deleteButtonClass}
                    disabled={readOnly || deletingSource === factor.energy_source}
                  >
                    {deletingSource === factor.energy_source ? "Removing..." : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
