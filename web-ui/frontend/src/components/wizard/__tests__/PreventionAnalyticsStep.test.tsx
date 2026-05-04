// @vitest-environment jsdom

import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import PreventionAnalyticsStep from "../PreventionAnalyticsStep";
import {
  getPreventionConfig,
  savePreventionConfig,
  testPreventionConnection,
} from "../../../api/client";

vi.mock("../../common/Tooltip", () => ({
  default: () => null,
}));

vi.mock("../../common/ErrorMessage", () => ({
  default: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock("../../common/LoadingSpinner", () => ({
  default: () => null,
}));

vi.mock("../../../api/client", () => ({
  getPreventionConfig: vi.fn(),
  savePreventionConfig: vi.fn(),
  testPreventionConnection: vi.fn(),
  toFriendlyErrorMessage: (error: unknown) =>
    error instanceof Error ? error.message : "Request failed",
}));

const CONFIG = {
  enabled: false,
  endpoint_url: "",
  endpoint_source: "none",
  env_override: false,
  auth_token_configured: false,
  auth_token_masked: "",
  auth_mode: "none",
  keycloak_token_url: "",
  keycloak_client_id: "",
  keycloak_client_secret_configured: false,
  keycloak_client_secret_masked: "",
  keycloak_scope: "",
  data_max_age_minutes: 1440,
  state: "disabled",
  verified: false,
  message: "PREVENTION is disabled until a URL is configured.",
  checked_at: null,
  data_state: "missing",
  data_message: "No PREVENTION export manifest has been generated yet.",
  data_updated_at: null,
  data_record_count: null,
};

describe("PreventionAnalyticsStep", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(getPreventionConfig).mockResolvedValue(CONFIG);
    vi.mocked(savePreventionConfig).mockResolvedValue(CONFIG);
    vi.mocked(testPreventionConnection).mockResolvedValue({
      success: true,
      state: "healthy",
      message: "PREVENTION endpoint is reachable and analytics are loaded.",
      checked_at: "2026-04-29T00:00:00+00:00",
    });
  });

  it("renders PREVENTION analytics fields", async () => {
    render(<PreventionAnalyticsStep onComplete={vi.fn()} onSkip={vi.fn()} />);

    expect(await screen.findByText("PREVENTION Analytics")).toBeTruthy();
    expect(screen.getByLabelText("PREVENTION Endpoint URL")).toBeTruthy();
    expect(screen.getByLabelText("Data Freshness Limit")).toBeTruthy();
    expect(screen.getByLabelText("PREVENTION Auth Mode")).toBeTruthy();
  });

  it("allows skipping with PREVENTION disabled", async () => {
    const onSkip = vi.fn();
    render(<PreventionAnalyticsStep onComplete={vi.fn()} onSkip={onSkip} />);

    fireEvent.click(await screen.findByRole("button", { name: "Skip" }));

    await waitFor(() => expect(savePreventionConfig).toHaveBeenCalledWith({
      enabled: false,
      endpoint_url: "",
      data_max_age_minutes: 1440,
      auth_mode: "none",
    }));
    expect(onSkip).toHaveBeenCalledOnce();
  });

  it("requires endpoint URL when enabled", async () => {
    render(<PreventionAnalyticsStep onComplete={vi.fn()} onSkip={vi.fn()} />);

    fireEvent.click(
      await screen.findByRole("checkbox", {
        name: /Enable PREVENTION analytics/,
      }),
    );
    fireEvent.click(screen.getByRole("button", { name: "Save & Continue" }));

    expect(
      await screen.findByText("PREVENTION endpoint URL is required when analytics are enabled."),
    ).toBeTruthy();
    expect(savePreventionConfig).not.toHaveBeenCalled();
  });

  it("tests the configured PREVENTION endpoint", async () => {
    render(<PreventionAnalyticsStep onComplete={vi.fn()} onSkip={vi.fn()} />);

    fireEvent.click(
      await screen.findByRole("checkbox", {
        name: /Enable PREVENTION analytics/,
      }),
    );
    fireEvent.change(screen.getByLabelText("PREVENTION Endpoint URL"), {
      target: { value: "http://prevention:8081" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Test Connection" }));

    await waitFor(() => expect(testPreventionConnection).toHaveBeenCalledWith({
      endpoint_url: "http://prevention:8081",
      auth_mode: "none",
      auth_token: "",
      keycloak_token_url: "",
      keycloak_client_id: "",
      keycloak_client_secret: "",
      keycloak_scope: "",
    }));
    expect(await screen.findByText(/Test passed:/)).toBeTruthy();
  });

  it("shows bearer token field when bearer auth is selected", async () => {
    render(<PreventionAnalyticsStep onComplete={vi.fn()} onSkip={vi.fn()} />);

    fireEvent.click(
      await screen.findByRole("checkbox", {
        name: /Enable PREVENTION analytics/,
      }),
    );
    fireEvent.change(screen.getByLabelText("PREVENTION Auth Mode"), {
      target: { value: "bearer" },
    });

    expect(screen.getByLabelText("Auth Token Optional")).toBeTruthy();
  });
});
