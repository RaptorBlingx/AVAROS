import { useCallback, useMemo, useState } from "react";

import { createProductionEntry, toFriendlyErrorMessage } from "../../api/client";
import type { ProductionRecordRequest } from "../../api/types";
import BrandSelect from "../common/BrandSelect";
import DatePickerInput from "../common/DatePickerInput";
import LoadingSpinner from "../common/LoadingSpinner";

type ManualEntryFormProps = {
  onCreated: () => void;
  onNotify: (type: "success" | "error", message: string) => void;
};

type ManualFormState = {
  record_date: string;
  asset_id: string;
  production_count: string;
  good_count: string;
  material_consumed_kg: string;
  shift: string;
  batch_id: string;
  notes: string;
};

type FormErrors = Partial<Record<keyof ManualFormState, string>>;

function todayIsoDate(): string {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

const INITIAL_FORM: ManualFormState = {
  record_date: todayIsoDate(),
  asset_id: "",
  production_count: "",
  good_count: "",
  material_consumed_kg: "",
  shift: "",
  batch_id: "",
  notes: "",
};

const SHIFT_OPTIONS = [
  { value: "", label: "Not specified" },
  { value: "morning", label: "Morning" },
  { value: "evening", label: "Evening" },
  { value: "night", label: "Night" },
];

function parseNonNegativeInteger(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  if (!Number.isInteger(parsed) || parsed < 0) return null;
  return parsed;
}

function parseNonNegativeNumber(value: string): number | null {
  if (value.trim() === "") return null;
  const parsed = Number(value);
  if (Number.isNaN(parsed) || parsed < 0) return null;
  return parsed;
}

export default function ManualEntryForm({ onCreated, onNotify }: ManualEntryFormProps) {
  const [form, setForm] = useState<ManualFormState>(INITIAL_FORM);
  const [errors, setErrors] = useState<FormErrors>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const maxDate = useMemo(() => todayIsoDate(), []);

  const validate = useCallback((value: ManualFormState): FormErrors => {
    const nextErrors: FormErrors = {};

    if (!value.record_date) {
      nextErrors.record_date = "Date is required.";
    } else if (value.record_date > todayIsoDate()) {
      nextErrors.record_date = "Date cannot be in the future.";
    }

    if (!value.asset_id.trim()) {
      nextErrors.asset_id = "Asset ID is required.";
    }

    const productionCount = parseNonNegativeInteger(value.production_count);
    const goodCount = parseNonNegativeInteger(value.good_count);
    const materialConsumed = parseNonNegativeNumber(value.material_consumed_kg);

    if (productionCount === null) {
      nextErrors.production_count = "Production count must be an integer >= 0.";
    }
    if (goodCount === null) {
      nextErrors.good_count = "Good count must be an integer >= 0.";
    }
    if (materialConsumed === null) {
      nextErrors.material_consumed_kg = "Material consumed must be a number >= 0.";
    }
    if (
      productionCount !== null &&
      goodCount !== null &&
      goodCount > productionCount
    ) {
      nextErrors.good_count = "Good count cannot exceed production count.";
    }

    return nextErrors;
  }, []);

  const handleSubmit = useCallback(
    async (event: React.FormEvent) => {
      event.preventDefault();

      const nextErrors = validate(form);
      setErrors(nextErrors);
      if (Object.keys(nextErrors).length > 0) {
        onNotify("error", "Please fix form validation errors.");
        return;
      }

      const payload: ProductionRecordRequest = {
        record_date: form.record_date,
        asset_id: form.asset_id.trim(),
        production_count: Number(form.production_count),
        good_count: Number(form.good_count),
        material_consumed_kg: Number(form.material_consumed_kg),
        shift: form.shift.trim() || undefined,
        batch_id: form.batch_id.trim() || undefined,
        notes: form.notes.trim() || undefined,
      };

      setIsSubmitting(true);
      try {
        await createProductionEntry(payload);
        setForm({ ...INITIAL_FORM, record_date: todayIsoDate() });
        setErrors({});
        onCreated();
        onNotify("success", "Production entry added.");
      } catch (error) {
        onNotify("error", toFriendlyErrorMessage(error));
      } finally {
        setIsSubmitting(false);
      }
    },
    [form, onCreated, onNotify, validate],
  );

  return (
    <form className="space-y-4" onSubmit={(event) => void handleSubmit(event)}>
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Record Date
          </span>
          <DatePickerInput
            value={form.record_date}
            onChange={(next) => setForm((prev) => ({ ...prev, record_date: next }))}
            max={maxDate}
          />
          {errors.record_date && <p className="m-0 mt-1 text-xs text-rose-600">{errors.record_date}</p>}
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Asset ID
          </span>
          <input
            type="text"
            value={form.asset_id}
            onChange={(event) => setForm((prev) => ({ ...prev, asset_id: event.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="Line-1"
          />
          {errors.asset_id && <p className="m-0 mt-1 text-xs text-rose-600">{errors.asset_id}</p>}
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Production Count
          </span>
          <input
            type="number"
            min={0}
            step={1}
            value={form.production_count}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, production_count: event.target.value }))
            }
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="0"
          />
          {errors.production_count && <p className="m-0 mt-1 text-xs text-rose-600">{errors.production_count}</p>}
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Good Count
          </span>
          <input
            type="number"
            min={0}
            step={1}
            value={form.good_count}
            onChange={(event) => setForm((prev) => ({ ...prev, good_count: event.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="0"
          />
          {errors.good_count && <p className="m-0 mt-1 text-xs text-rose-600">{errors.good_count}</p>}
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Material Consumed (kg)
          </span>
          <input
            type="number"
            min={0}
            step={0.01}
            value={form.material_consumed_kg}
            onChange={(event) =>
              setForm((prev) => ({ ...prev, material_consumed_kg: event.target.value }))
            }
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="0.00"
          />
          {errors.material_consumed_kg && (
            <p className="m-0 mt-1 text-xs text-rose-600">{errors.material_consumed_kg}</p>
          )}
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Shift
          </span>
          <BrandSelect
            value={form.shift}
            onChange={(next) => setForm((prev) => ({ ...prev, shift: next }))}
            options={SHIFT_OPTIONS}
          />
        </label>

        <label className="block text-sm">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Batch ID
          </span>
          <input
            type="text"
            value={form.batch_id}
            onChange={(event) => setForm((prev) => ({ ...prev, batch_id: event.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="B-2026-010"
          />
        </label>

        <label className="block text-sm xl:col-span-2">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
            Notes
          </span>
          <textarea
            rows={2}
            value={form.notes}
            onChange={(event) => setForm((prev) => ({ ...prev, notes: event.target.value }))}
            className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
            placeholder="Optional operator notes"
          />
        </label>
      </div>

      <div className="flex items-center gap-3">
        <button
          type="submit"
          disabled={isSubmitting}
          className="btn-brand-primary rounded-lg px-4 py-2 text-sm font-semibold disabled:cursor-not-allowed disabled:opacity-60"
        >
          Add Entry
        </button>
        {isSubmitting && <LoadingSpinner size="sm" label="Saving entry..." />}
      </div>
    </form>
  );
}
