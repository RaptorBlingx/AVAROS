import {
  CategoryScale,
  Chart as ChartJS,
  Filler,
  Legend,
  LineElement,
  LinearScale,
  PointElement,
  Tooltip,
  type ChartData,
  type ChartOptions,
} from "chart.js";
import { useMemo } from "react";
import { Line } from "react-chartjs-2";

import type { SnapshotResponse } from "../../api/types";
import { useTheme } from "../common/ThemeProvider";

ChartJS.register(
  CategoryScale,
  LinearScale,
  PointElement,
  LineElement,
  Tooltip,
  Legend,
  Filler
);

type KPITrendChartProps = {
  metricLabel: string;
  unit: string;
  snapshots: SnapshotResponse[];
  baselineValue: number;
  targetValue: number;
};

function formatLabel(input: string): string {
  const date = new Date(input);
  if (Number.isNaN(date.getTime())) {
    return input;
  }
  const mm = String(date.getMonth() + 1).padStart(2, "0");
  const dd = String(date.getDate()).padStart(2, "0");
  const hh = String(date.getHours()).padStart(2, "0");
  const min = String(date.getMinutes()).padStart(2, "0");
  return `${mm}/${dd} ${hh}:${min}`;
}

export default function KPITrendChart({
  metricLabel,
  unit,
  snapshots,
  baselineValue,
  targetValue,
}: KPITrendChartProps) {
  const { isDark } = useTheme();

  const chartData = useMemo<ChartData<"line">>(() => {
    const labels = snapshots.map((item) => formatLabel(item.measured_at));
    const values = snapshots.map((item) => item.value);

    return {
      labels,
      datasets: [
        {
          label: `${metricLabel} (${unit})`,
          data: values,
          borderColor: "rgb(14, 165, 233)",
          backgroundColor: "rgba(14, 165, 233, 0.15)",
          borderWidth: 2,
          pointRadius: 2,
          pointHoverRadius: 4,
          fill: true,
          tension: 0.25,
        },
        {
          label: "Baseline",
          data: labels.map(() => baselineValue),
          borderColor: "rgb(99, 102, 241)",
          borderWidth: 1.5,
          borderDash: [6, 6],
          pointRadius: 0,
          fill: false,
          tension: 0,
        },
        {
          label: "Target",
          data: labels.map(() => targetValue),
          borderColor: "rgb(16, 185, 129)",
          borderWidth: 1.5,
          borderDash: [2, 5],
          pointRadius: 0,
          fill: false,
          tension: 0,
        },
      ],
    };
  }, [baselineValue, metricLabel, snapshots, targetValue, unit]);

  const options = useMemo<ChartOptions<"line">>(
    () => ({
      responsive: true,
      maintainAspectRatio: false,
      interaction: {
        intersect: false,
        mode: "index",
      },
      plugins: {
        legend: {
          display: true,
          labels: {
            color: isDark ? "#cbd5e1" : "#334155",
            boxWidth: 12,
            boxHeight: 12,
          },
        },
        tooltip: {
          backgroundColor: isDark ? "#0f172a" : "#ffffff",
          titleColor: isDark ? "#e2e8f0" : "#0f172a",
          bodyColor: isDark ? "#cbd5e1" : "#334155",
          borderColor: isDark ? "#334155" : "#cbd5e1",
          borderWidth: 1,
        },
      },
      scales: {
        x: {
          ticks: {
            color: isDark ? "#94a3b8" : "#64748b",
            maxRotation: 0,
            autoSkip: true,
          },
          grid: {
            color: isDark ? "rgba(148,163,184,0.15)" : "rgba(148,163,184,0.2)",
          },
        },
        y: {
          ticks: {
            color: isDark ? "#94a3b8" : "#64748b",
          },
          grid: {
            color: isDark ? "rgba(148,163,184,0.15)" : "rgba(148,163,184,0.2)",
          },
        },
      },
    }),
    [isDark]
  );

  if (snapshots.length === 0) {
    return (
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500 dark:border-slate-600 dark:bg-slate-900/30 dark:text-slate-400">
        No data yet
      </div>
    );
  }

  return (
    <div className="h-[260px] min-w-[320px] rounded-xl border border-slate-200 bg-white p-3 dark:border-slate-700 dark:bg-slate-900/40">
      <Line data={chartData} options={options} />
    </div>
  );
}
