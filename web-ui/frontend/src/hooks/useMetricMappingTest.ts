import { useCallback, useState } from "react";

import { getPlatformConfig, testMetricMapping, toFriendlyErrorMessage } from "../api/client";

export type MetricTestState =
  | { status: "loading" }
  | { status: "success"; value: number }
  | { status: "error"; error: string };

type TestableMetricRow = {
  canonical_metric: string;
  endpoint: string;
  json_path: string;
};

type UseMetricMappingTestOptions = {
  disabled?: boolean;
  resolveRow: (rowId: string) => TestableMetricRow | undefined;
  onError?: (message: string) => void;
};

function clearRowState(
  previous: Record<string, MetricTestState>,
  rowId: string,
): Record<string, MetricTestState> {
  if (!previous[rowId]) {
    return previous;
  }
  const copy = { ...previous };
  delete copy[rowId];
  return copy;
}

export default function useMetricMappingTest({
  disabled = false,
  resolveRow,
  onError,
}: UseMetricMappingTestOptions) {
  const [testStateByRow, setTestStateByRow] = useState<Record<string, MetricTestState>>({});

  const resetRowTestState = useCallback((rowId: string) => {
    setTestStateByRow((prev) => clearRowState(prev, rowId));
  }, []);

  const clearAllTestState = useCallback(() => {
    setTestStateByRow({});
  }, []);

  const testRowMapping = useCallback(async (rowId: string) => {
    if (disabled) {
      return;
    }
    const row = resolveRow(rowId);
    if (!row) {
      return;
    }
    if (!row.endpoint.trim() || !row.json_path.trim()) {
      const errorMessage =
        "Endpoint and JSON path are required before testing.";
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: errorMessage,
        },
      }));
      onError?.(errorMessage);
      return;
    }

    setTestStateByRow((prev) => ({ ...prev, [rowId]: { status: "loading" } }));
    try {
      const config = await getPlatformConfig();
      if (!config.api_url.trim()) {
        const errorMessage = "Platform base URL is not configured yet.";
        setTestStateByRow((prev) => ({
          ...prev,
          [rowId]: {
            status: "error",
            error: errorMessage,
          },
        }));
        onError?.(errorMessage);
        return;
      }

      const response = await testMetricMapping({
        base_url: config.api_url,
        endpoint: row.endpoint.trim(),
        json_path: row.json_path.trim(),
        auth_type:
          config.extra_settings.auth_type === "cookie"
            ? "cookie"
            : config.extra_settings.auth_type === "none"
            ? "none"
            : "bearer",
        auth_token: config.api_key,
      });
      if (response.success && typeof response.value === "number") {
        setTestStateByRow((prev) => ({
          ...prev,
          [rowId]: { status: "success", value: response.value as number },
        }));
        return;
      }
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: response.error ?? "Mapping test failed.",
        },
      }));
      onError?.(response.error ?? "Mapping test failed.");
    } catch (error: unknown) {
      const errorMessage = toFriendlyErrorMessage(error);
      setTestStateByRow((prev) => ({
        ...prev,
        [rowId]: {
          status: "error",
          error: errorMessage,
        },
      }));
      onError?.(errorMessage);
    }
  }, [disabled, onError, resolveRow]);

  return {
    testStateByRow,
    testRowMapping,
    resetRowTestState,
    clearAllTestState,
  };
}
