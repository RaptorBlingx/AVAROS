// @vitest-environment jsdom

import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import type { SystemStatusResponse } from "../../../api/types";
import PlatformSetupStep from "../PlatformSetupStep";

vi.mock("../../common/Tooltip", () => ({
  default: () => null,
}));

vi.mock("../../common/ConnectionTestResult", () => ({
  default: () => null,
}));

vi.mock("../../common/ErrorMessage", () => ({
  default: ({ message }: { message: string }) => <div>{message}</div>,
}));

vi.mock("../../common/LoadingSpinner", () => ({
  default: () => null,
}));

vi.mock("../../../api/client", () => ({
  listProfiles: vi.fn().mockResolvedValue({ active_profile: "reneryo", profiles: [{ name: "reneryo", platform_type: "custom_rest", is_builtin: false, is_active: true }] }),
  createProfile: vi.fn(),
  activateProfile: vi.fn(),
  getProfile: vi.fn(),
}));

const STATUS: SystemStatusResponse = {
  configured: false,
  active_adapter: "custom_rest",
  platform_type: "custom_rest",
  loaded_intents: 0,
  database_connected: true,
  version: "0.1.0",
};

function renderStep() {
  render(
    <PlatformSetupStep
      status={STATUS}
      statusLoading={false}
      statusError=""
      authType="api_key"
      apiUrl=""
      apiKey=""
      formError=""
      testResult={null}
      testError=""
      isTesting={false}
      isSaving={false}
      selectedProfile="reneryo"
      onProfileChange={vi.fn()}
      onAuthTypeChange={vi.fn()}
      onApiUrlChange={vi.fn()}
      onApiKeyChange={vi.fn()}
      onTestConnection={vi.fn()}
      onSaveAndContinue={vi.fn()}
    />,
  );
}

describe("PlatformSetupStep", () => {
  it("renders the step header", () => {
    renderStep();
    expect(screen.getByText("Platform Setup")).toBeTruthy();
  });

  it("renders the Save & Continue button", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Save & Continue" })).toBeTruthy();
  });

  it("renders the Test Connection button", () => {
    renderStep();
    expect(screen.getByRole("button", { name: "Test Connection" })).toBeTruthy();
  });

  it("renders the + New Profile button", async () => {
    renderStep();
    expect(await screen.findByRole("button", { name: "+ New Profile" })).toBeTruthy();
  });
});
