import { useMemo } from "react";

import type { ProductionRecordResponse } from "../../api/types";
import LoadingSpinner from "../common/LoadingSpinner";

type ProductionDataTableProps = {
  records: ProductionRecordResponse[];
  total: number;
  page: number;
  pageSize: number;
  loading: boolean;
  deletingId: number | null;
  onPageChange: (nextPage: number) => void;
  onDelete: (id: number) => void;
};

export default function ProductionDataTable({
  records,
  total,
  page,
  pageSize,
  loading,
  deletingId,
  onPageChange,
  onDelete,
}: ProductionDataTableProps) {
  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / pageSize)), [pageSize, total]);

  if (records.length === 0) {
    return (
      <div className="brand-surface rounded-xl px-5 py-6 text-center">
        <div className="mx-auto mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-white/90 text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
          <svg viewBox="0 0 24 24" className="h-5 w-5" fill="none" stroke="currentColor">
            <path d="M5 12h14M12 5v14" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </div>
        <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
          No production entries
        </h4>
        <p className="m-0 mt-1 text-sm text-slate-600 dark:text-slate-300">
          Add manual entries or upload CSV to populate production records.
        </p>
        {loading && (
          <div className="mt-3 flex justify-center">
            <LoadingSpinner size="sm" label="Loading production data..." />
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="brand-surface relative rounded-xl p-4">
      {loading && (
        <div className="absolute inset-0 z-10 flex items-center justify-center rounded-xl bg-white/55 backdrop-blur-[1px] dark:bg-slate-900/50">
          <LoadingSpinner size="sm" label="Refreshing records..." />
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="min-w-[960px] w-full text-left text-sm">
          <thead>
            <tr className="border-b border-slate-200 dark:border-slate-700">
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Date</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Asset</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Produced</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Good</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Material (kg)</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Shift</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Batch</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Notes</th>
              <th className="px-2 py-2 font-semibold text-slate-700 dark:text-slate-200">Action</th>
            </tr>
          </thead>
          <tbody>
            {records.map((row) => (
              <tr key={row.id} className="border-b border-slate-100 dark:border-slate-800">
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.record_date}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.asset_id}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.production_count}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.good_count}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.material_consumed_kg}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.shift || "-"}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.batch_id || "-"}</td>
                <td className="px-2 py-2 text-slate-700 dark:text-slate-200">{row.notes || "-"}</td>
                <td className="px-2 py-2">
                  <button
                    type="button"
                    onClick={() => onDelete(row.id)}
                    disabled={deletingId === row.id}
                    className="rounded-lg border border-rose-300 bg-rose-50 px-3 py-1 text-xs font-semibold text-rose-700 transition hover:bg-rose-100 disabled:cursor-not-allowed disabled:opacity-60 dark:border-rose-500/40 dark:bg-rose-950/35 dark:text-rose-200"
                  >
                    {deletingId === row.id ? "Deleting..." : "Delete"}
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {total > pageSize && (
        <div className="mt-4 flex items-center justify-between gap-2 text-sm">
          <p className="m-0 text-slate-600 dark:text-slate-300">
            Page {page} / {totalPages}
          </p>
          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => onPageChange(page - 1)}
              disabled={page <= 1}
              className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              Previous
            </button>
            <button
              type="button"
              onClick={() => onPageChange(page + 1)}
              disabled={page >= totalPages}
              className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold disabled:cursor-not-allowed disabled:opacity-60"
            >
              Next
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
