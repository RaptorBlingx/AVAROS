import { useCallback, useEffect, useMemo, useState } from "react";

import {
  deleteProductionEntry,
  getProductionSummary,
  listProductionData,
  toFriendlyErrorMessage,
} from "../api/client";
import type {
  ProductionRecordListResponse,
  ProductionRecordResponse,
  ProductionSummaryResponse,
} from "../api/types";
import CSVUploadPanel from "../components/production/CSVUploadPanel";
import ManualEntryForm from "../components/production/ManualEntryForm";
import ProductionDataTable from "../components/production/ProductionDataTable";
import DatePickerInput from "../components/common/DatePickerInput";
import ErrorMessage from "../components/common/ErrorMessage";
import LoadingSpinner from "../components/common/LoadingSpinner";
import OnboardingOverlay from "../components/common/OnboardingOverlay";
import {
  ONBOARDING_RERUN_EVENT,
  shouldOpenOnboardingForScope,
  type OnboardingRerunDetail,
} from "../components/common/onboarding";
import Toast from "../components/common/Toast";
import type { ToastItem } from "../components/common/Toast";

type TabKey = "csv" | "manual";

const PAGE_SIZE = 20;

function todayIsoDate(): string {
  const now = new Date();
  return now.toISOString().slice(0, 10);
}

function firstDayIsoDate(): string {
  const now = new Date();
  const firstDay = new Date(now.getFullYear(), now.getMonth(), 1);
  return firstDay.toISOString().slice(0, 10);
}

export default function ProductionData() {
  const [activeTab, setActiveTab] = useState<TabKey>("csv");
  const [toasts, setToasts] = useState<ToastItem[]>([]);

  const [records, setRecords] = useState<ProductionRecordResponse[]>([]);
  const [total, setTotal] = useState(0);
  const [listLoading, setListLoading] = useState(true);
  const [listError, setListError] = useState<string>("");
  const [deletingId, setDeletingId] = useState<number | null>(null);

  const [assetFilter, setAssetFilter] = useState("");
  const [startDateFilter, setStartDateFilter] = useState(firstDayIsoDate());
  const [endDateFilter, setEndDateFilter] = useState(todayIsoDate());
  const [appliedAssetFilter, setAppliedAssetFilter] = useState("");
  const [appliedStartDateFilter, setAppliedStartDateFilter] = useState(
    firstDayIsoDate(),
  );
  const [appliedEndDateFilter, setAppliedEndDateFilter] = useState(
    todayIsoDate(),
  );
  const [page, setPage] = useState(1);

  const [summary, setSummary] = useState<ProductionSummaryResponse | null>(
    null,
  );
  const [summaryLoading, setSummaryLoading] = useState(false);
  const [filterDateError, setFilterDateError] = useState<string>("");
  const [onboardingOpen, setOnboardingOpen] = useState(false);

  const notify = useCallback((type: "success" | "error", message: string) => {
    setToasts((prev) => [
      ...prev,
      { id: Date.now() + Math.random(), type, message },
    ]);
  }, []);

  const dismissToast = useCallback((id: number) => {
    setToasts((prev) => prev.filter((toast) => toast.id !== id));
  }, []);

  const loadRecords = useCallback(async () => {
    setListLoading(true);
    setListError("");

    try {
      const response: ProductionRecordListResponse = await listProductionData({
        asset_id: appliedAssetFilter.trim() || undefined,
        start_date: appliedStartDateFilter || undefined,
        end_date: appliedEndDateFilter || undefined,
      });

      const sorted = [...response.records].sort((a, b) => {
        const dateDiff =
          new Date(b.record_date).getTime() - new Date(a.record_date).getTime();
        if (dateDiff !== 0) {
          return dateDiff;
        }
        return b.id - a.id;
      });

      setRecords(sorted);
      setTotal(response.total);
      setPage(1);
    } catch (error) {
      setListError(toFriendlyErrorMessage(error));
      setRecords([]);
      setTotal(0);
    } finally {
      setListLoading(false);
    }
  }, [appliedAssetFilter, appliedEndDateFilter, appliedStartDateFilter]);

  const loadSummary = useCallback(async () => {
    if (
      appliedStartDateFilter &&
      appliedEndDateFilter &&
      appliedStartDateFilter > appliedEndDateFilter
    ) {
      setSummary(null);
      return;
    }
    if (!appliedAssetFilter.trim()) {
      setSummary(null);
      return;
    }

    setSummaryLoading(true);
    try {
      const data = await getProductionSummary(
        appliedAssetFilter.trim(),
        appliedStartDateFilter,
        appliedEndDateFilter,
      );
      setSummary(data);
    } catch (error) {
      console.warn("Failed to load production summary:", error);
      setSummary(null);
    } finally {
      setSummaryLoading(false);
    }
  }, [appliedAssetFilter, appliedEndDateFilter, appliedStartDateFilter]);

  useEffect(() => {
    void loadRecords();
  }, [loadRecords]);

  useEffect(() => {
    void loadSummary();
  }, [loadSummary]);

  useEffect(() => {
    const onRerun = (event: Event) => {
      const detail = (event as CustomEvent<OnboardingRerunDetail>).detail;
      if (detail && shouldOpenOnboardingForScope(detail.scope, "production")) {
        setOnboardingOpen(true);
      }
    };
    window.addEventListener(ONBOARDING_RERUN_EVENT, onRerun);
    return () => window.removeEventListener(ONBOARDING_RERUN_EVENT, onRerun);
  }, []);

  const paginatedRecords = useMemo(() => {
    const start = (page - 1) * PAGE_SIZE;
    return records.slice(start, start + PAGE_SIZE);
  }, [page, records]);

  const handleDelete = useCallback(
    async (id: number) => {
      setDeletingId(id);
      try {
        await deleteProductionEntry(id);
        notify("success", "Entry deleted.");
        await loadRecords();
      } catch (error) {
        notify("error", toFriendlyErrorMessage(error));
      } finally {
        setDeletingId(null);
      }
    },
    [loadRecords, notify],
  );

  const handleApplyFilters = useCallback(() => {
    if (startDateFilter && endDateFilter && startDateFilter > endDateFilter) {
      setFilterDateError("Start date cannot be after end date.");
      return;
    }
    setFilterDateError("");
    setAppliedAssetFilter(assetFilter);
    setAppliedStartDateFilter(startDateFilter);
    setAppliedEndDateFilter(endDateFilter);
  }, [assetFilter, endDateFilter, startDateFilter]);

  const handleResetFilters = useCallback(() => {
    setFilterDateError("");
    setAssetFilter("");
    setStartDateFilter("");
    setEndDateFilter("");
    setAppliedAssetFilter("");
    setAppliedStartDateFilter("");
    setAppliedEndDateFilter("");
  }, []);

  const onboardingSteps = useMemo(() => {
    const commonSteps = [
      {
        title: "Production Data Overview",
        description:
          "Upload CSV files or enter production records manually from this page.",
        selector: '[data-onboarding-target="production-header"]',
      },
      {
        title: "CSV and Manual Tabs",
        description:
          "Choose CSV upload or manual entry based on your operator workflow.",
        selector: '[data-onboarding-target="production-tabs"]',
      },
    ];

    if (activeTab === "manual") {
      return [
        ...commonSteps,
        {
          title: "Add Manual Entry",
          description:
            "Fill record date, asset, counts, material, and notes to create an entry.",
          selector: '[data-onboarding-target="production-manual-form"]',
        },
        {
          title: "Filters and Summary",
          description:
            "Filter by asset/date range and review summary statistics for the selection.",
          selector: '[data-onboarding-target="production-filters"]',
        },
        {
          title: "Production Records",
          description:
            "Review saved entries and remove incorrect records from the data table.",
          selector: '[data-onboarding-target="production-data-table"]',
        },
      ] as const;
    }

    return [
      ...commonSteps,
      {
        title: "CSV Upload",
        description:
          "Import production records from ERP/MES exports using drag-and-drop CSV upload.",
        selector: '[data-onboarding-target="production-csv-upload"]',
      },
    ] as const;
  }, [activeTab]);

  return (
    <section className="space-y-4">
      <Toast toasts={toasts} onDismiss={dismissToast} />

      <header
        className="brand-hero rounded-2xl p-6"
        data-onboarding-target="production-header"
      >
        <p className="m-0 brand-title-gradient text-xs font-semibold uppercase tracking-[0.14em]">
          AVAROS Control Panel
        </p>
        <h2 className="m-0 mt-2 text-2xl font-semibold text-slate-900 dark:text-slate-100">
          Production Data
        </h2>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          Upload CSV exports or add production records manually for KPI
          calculations.
        </p>
      </header>

      <div
        className="brand-panel rounded-2xl p-4"
        data-onboarding-target="production-tabs"
      >
        <div className="flex flex-wrap gap-2">
          <button
            type="button"
            onClick={() => setActiveTab("csv")}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              activeTab === "csv" ? "btn-brand-primary" : "btn-brand-subtle"
            }`}
          >
            CSV Upload
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("manual")}
            className={`rounded-lg px-4 py-2 text-sm font-semibold transition ${
              activeTab === "manual" ? "btn-brand-primary" : "btn-brand-subtle"
            }`}
          >
            Manual Entry
          </button>
        </div>
      </div>

      {activeTab === "csv" ? (
        <div data-onboarding-target="production-csv-upload">
          <CSVUploadPanel
            onUploadComplete={() => void loadRecords()}
            onNotify={notify}
          />
        </div>
      ) : (
        <>
          <div
            className="brand-panel rounded-2xl p-4"
            data-onboarding-target="production-manual-form"
          >
            <h3 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
              Add Manual Entry
            </h3>
            <div className="mt-3">
              <ManualEntryForm
                onCreated={() => void loadRecords()}
                onNotify={notify}
              />
            </div>
          </div>

          <div
            className="brand-panel rounded-2xl p-4"
            data-onboarding-target="production-filters"
          >
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 xl:grid-cols-5">
              <label className="block text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                  Asset ID Filter
                </span>
                <input
                  type="text"
                  value={assetFilter}
                  onChange={(event) => setAssetFilter(event.target.value)}
                  placeholder="Line-1"
                  className="mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
                />
              </label>

              <label className="block text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                  Start Date
                </span>
                <DatePickerInput
                  value={startDateFilter}
                  onChange={setStartDateFilter}
                  max={todayIsoDate()}
                />
              </label>

              <label className="block text-sm">
                <span className="text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                  End Date
                </span>
                <DatePickerInput
                  value={endDateFilter}
                  onChange={setEndDateFilter}
                  min={startDateFilter}
                  max={todayIsoDate()}
                />
              </label>

              <div className="flex items-end gap-2">
                <button
                  type="button"
                  onClick={handleApplyFilters}
                  disabled={!!filterDateError}
                  className="btn-brand-subtle w-full rounded-lg px-4 py-2 text-sm font-semibold"
                >
                  Apply Filters
                </button>
                <button
                  type="button"
                  onClick={handleResetFilters}
                  className="btn-brand-subtle inline-flex items-center justify-center rounded-lg px-3 py-2 text-sm font-semibold"
                  aria-label="Reset filters"
                  title="Reset filters"
                >
                  <svg
                    className="h-4 w-4"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                  >
                    <path
                      d="M3 12a9 9 0 1015.36-6.36M3 4v6h6"
                      strokeWidth="2"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </button>
              </div>
            </div>
            {filterDateError && (
              <p className="m-0 mt-2 text-xs text-rose-600 dark:text-rose-300">
                {filterDateError}
              </p>
            )}

            <div className="mt-4">
              {summary ? (
                <div className="brand-surface rounded-xl p-4 text-sm text-slate-700 dark:text-slate-200">
                  <div className="flex items-center justify-between gap-3">
                    <p className="m-0 font-semibold">Production Summary</p>
                    {summaryLoading && (
                      <LoadingSpinner size="sm" label="Updating..." />
                    )}
                  </div>
                  <div className="mt-2 grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
                    <p className="m-0">Asset: {summary.asset_id}</p>
                    <p className="m-0">Records: {summary.record_count}</p>
                    <p className="m-0">
                      Total Produced: {summary.total_produced}
                    </p>
                    <p className="m-0">Total Good: {summary.total_good}</p>
                    <p className="m-0">
                      Total Material: {summary.total_material_kg} kg
                    </p>
                    <p className="m-0">
                      Efficiency: {summary.material_efficiency_pct.toFixed(2)}%
                    </p>
                    <p className="m-0">From: {summary.start_date}</p>
                    <p className="m-0">To: {summary.end_date}</p>
                  </div>
                </div>
              ) : (
                <div className="brand-surface rounded-xl px-5 py-6 text-center">
                  <div className="mx-auto mb-2 inline-flex h-10 w-10 items-center justify-center rounded-full border border-slate-300 bg-white/90 text-slate-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-300">
                    <svg
                      viewBox="0 0 24 24"
                      className="h-5 w-5"
                      fill="none"
                      stroke="currentColor"
                    >
                      <path
                        d="M5 12h14M12 5v14"
                        strokeWidth="2"
                        strokeLinecap="round"
                      />
                    </svg>
                  </div>
                  <h4 className="m-0 text-sm font-semibold text-slate-900 dark:text-slate-100">
                    No summary available
                  </h4>
                  <p className="m-0 mt-1 text-sm text-slate-600 dark:text-slate-300">
                    Set an Asset ID filter to load summary for the selected date
                    range.
                  </p>
                  {summaryLoading && (
                    <div className="mt-3 flex justify-center">
                      <LoadingSpinner
                        size="sm"
                        label="Loading production summary..."
                      />
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          <div data-onboarding-target="production-data-table">
            {listError ? (
              <ErrorMessage
                message={listError}
                onRetry={() => void loadRecords()}
              />
            ) : (
              <ProductionDataTable
                records={paginatedRecords}
                total={total}
                page={page}
                pageSize={PAGE_SIZE}
                loading={listLoading}
                deletingId={deletingId}
                onPageChange={setPage}
                onDelete={(id) => void handleDelete(id)}
              />
            )}
          </div>
        </>
      )}

      <OnboardingOverlay
        open={onboardingOpen}
        steps={onboardingSteps}
        onClose={() => setOnboardingOpen(false)}
      />
    </section>
  );
}
