// @vitest-environment jsdom

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import ConnectionSetupStep from "../ConnectionSetupStep";

function renderStep(authType: "api_key" | "cookie" | "none" = "api_key") {
  const onAuthTypeChange = vi.fn();
  render(
    <ConnectionSetupStep
      platformType="custom_rest"
      authType={authType}
      apiUrl="https://api.example.com"
      apiKey=""
      formError=""
      testResult={null}
      testError=""
      isTesting={false}
      isSaving={false}
      onAuthTypeChange={onAuthTypeChange}
      onApiUrlChange={vi.fn()}
      onApiKeyChange={vi.fn()}
      onTestConnection={vi.fn()}
      onSave={vi.fn()}
    />,
  );
  return { onAuthTypeChange };
}

describe("ConnectionSetupStep", () => {
  it("shows No Authentication option", () => {
    const { onAuthTypeChange } = renderStep();

    fireEvent.change(screen.getByDisplayValue("API Key"), {
      target: { value: "none" },
    });

    expect(onAuthTypeChange).toHaveBeenCalledWith("none");
  });

  it("hides credential input for none auth", () => {
    renderStep("none");

    expect(screen.queryByPlaceholderText(/enter your api key/i)).toBeNull();
    expect(screen.queryByPlaceholderText(/paste session cookie/i)).toBeNull();
  });
});
