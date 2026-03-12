import { describe, expect, it } from "vitest";

import { buildPayload } from "../Wizard";

describe("buildPayload", () => {
  it("sends empty api_key when auth type is none", () => {
    const payload = buildPayload({
      currentStep: 3,
      platformType: "custom_rest",
      authType: "none",
      apiUrl: "https://api.example.com",
      apiKey: "secret-should-not-be-sent",
    });

    expect(payload).toMatchObject({
      platform_type: "custom_rest",
      api_url: "https://api.example.com",
      api_key: "",
      extra_settings: { auth_type: "none" },
    });
  });

  it("keeps api_key for cookie and api_key auth types", () => {
    const cookiePayload = buildPayload({
      currentStep: 3,
      platformType: "reneryo",
      authType: "cookie",
      apiUrl: "https://api.reneryo.com",
      apiKey: "session-cookie",
    });
    const apiKeyPayload = buildPayload({
      currentStep: 3,
      platformType: "reneryo",
      authType: "api_key",
      apiUrl: "https://api.reneryo.com",
      apiKey: "bearer-key",
    });

    expect(cookiePayload).toMatchObject({
      api_key: "session-cookie",
      extra_settings: { auth_type: "cookie" },
    });
    expect(apiKeyPayload).toMatchObject({
      api_key: "bearer-key",
      extra_settings: { auth_type: "bearer" },
    });
  });

  it("keeps mock behavior unchanged", () => {
    const payload = buildPayload({
      currentStep: 3,
      platformType: "mock",
      authType: "api_key",
      apiUrl: "https://ignored.example.com",
      apiKey: "ignored-key",
    });

    expect(payload).toMatchObject({
      platform_type: "mock",
      api_url: "",
      api_key: "",
    });
  });
});
