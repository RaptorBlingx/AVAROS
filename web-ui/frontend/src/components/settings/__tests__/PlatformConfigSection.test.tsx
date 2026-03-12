// @vitest-environment jsdom

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type {
  PlatformConfigResponse,
  ProfileConfig,
  ProfileListResponse,
} from "../../../api/types";
import PlatformConfigSection from "../PlatformConfigSection";

vi.mock("../../../api/client", () => ({
  getPlatformConfig: vi.fn(),
  createPlatformConfig: vi.fn(),
  resetPlatformConfig: vi.fn(),
  testConnection: vi.fn(),
  listProfiles: vi.fn(),
  getProfile: vi.fn(),
  createProfile: vi.fn(),
  deleteProfile: vi.fn(),
  activateProfile: vi.fn(),
  toFriendlyErrorMessage: vi.fn((e: unknown) => String(e)),
}));

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

import {
  activateProfile,
  resetPlatformConfig,
  getProfile,
  getPlatformConfig,
  listProfiles,
} from "../../../api/client";

const mockGetPlatformConfig = vi.mocked(getPlatformConfig);
const mockListProfiles = vi.mocked(listProfiles);
const mockGetProfile = vi.mocked(getProfile);
const mockActivateProfile = vi.mocked(activateProfile);
const mockResetPlatformConfig = vi.mocked(resetPlatformConfig);

const DEFAULT_PLATFORM_CONFIG: PlatformConfigResponse = {
  platform_type: "mock",
  api_url: "",
  api_key: "****",
  extra_settings: {},
};

const MOCK_PROFILES: ProfileListResponse = {
  profiles: [
    {
      name: "mock",
      platform_type: "mock",
      is_active: true,
      is_builtin: true,
    },
    {
      name: "my-reneryo",
      platform_type: "reneryo",
      is_active: false,
      is_builtin: false,
    },
    {
      name: "custom-no-auth",
      platform_type: "custom_rest",
      is_active: false,
      is_builtin: false,
    },
  ],
  active_profile: "mock",
};

const MOCK_PROFILE_CONFIG: ProfileConfig = {
  name: "mock",
  platform_type: "mock",
  api_url: "",
  api_key: "****",
  extra_settings: {},
  is_builtin: true,
  is_active: true,
};

const RENERYO_PROFILE_CONFIG: ProfileConfig = {
  name: "my-reneryo",
  platform_type: "reneryo",
  api_url: "https://api.reneryo.com",
  api_key: "****abcd",
  extra_settings: { auth_type: "bearer" },
  is_builtin: false,
  is_active: false,
};

const CUSTOM_REST_NONE_PROFILE_CONFIG: ProfileConfig = {
  name: "custom-no-auth",
  platform_type: "custom_rest",
  api_url: "https://custom.example.com",
  api_key: "****",
  extra_settings: { auth_type: "none" },
  is_builtin: false,
  is_active: false,
};

function findPlatformSelect(container: HTMLElement): HTMLSelectElement | null {
  const selects = container.querySelectorAll<HTMLSelectElement>("select");
  return (
    Array.from(selects).find((s) => {
      const options = Array.from(s.options).map((o) => o.value);
      return options.includes("reneryo") && options.includes("custom_rest");
    }) ?? null
  );
}

type OnNotify = (type: "success" | "error", message: string) => void;

describe("PlatformConfigSection with ProfileSelector", () => {
  let onNotify: OnNotify & ReturnType<typeof vi.fn>;

  afterEach(() => {
    cleanup();
  });

  beforeEach(() => {
    vi.clearAllMocks();
    onNotify = vi.fn() as typeof onNotify;
    mockGetPlatformConfig.mockResolvedValue(DEFAULT_PLATFORM_CONFIG);
    mockListProfiles.mockResolvedValue(MOCK_PROFILES);
    mockGetProfile.mockImplementation(async (name: string) => {
      if (name === "mock") return MOCK_PROFILE_CONFIG;
      if (name === "my-reneryo") return RENERYO_PROFILE_CONFIG;
      if (name === "custom-no-auth") return CUSTOM_REST_NONE_PROFILE_CONFIG;
      throw new Error(`Unknown profile: ${name}`);
    });
    mockResetPlatformConfig.mockResolvedValue({
      status: "reset",
      platform_type: "mock",
    });
    vi.spyOn(window, "confirm").mockReturnValue(true);
  });

  it("renders profile selector and platform config form", async () => {
    const { container } = render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    await waitFor(() => {
      const platformSelect = findPlatformSelect(container);
      expect(platformSelect).not.toBeNull();
      expect(platformSelect!.value).toBe("mock");
    });
  });

  it("hides Edit button when mock (builtin) profile is active", async () => {
    const { container } = render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      const platformSelect = findPlatformSelect(container);
      expect(platformSelect).not.toBeNull();
    });

    expect(screen.queryByText("Edit")).toBeNull();
  });

  it("updates form fields when switching to a different profile", async () => {
    const { container } = render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-dropdown"), {
      target: { value: "my-reneryo" },
    });

    await waitFor(() => {
      expect(mockGetProfile).toHaveBeenCalledWith("my-reneryo");
    });

    await waitFor(() => {
      const platformSelect = findPlatformSelect(container);
      expect(platformSelect).not.toBeNull();
      expect(platformSelect!.value).toBe("reneryo");
    });
  });

  it("shows Edit button for non-builtin active profile after switch", async () => {
    const activatedConfig: ProfileConfig = {
      ...RENERYO_PROFILE_CONFIG,
      is_active: true,
    };
    mockActivateProfile.mockResolvedValue(activatedConfig);

    const updatedProfiles: ProfileListResponse = {
      profiles: [
        {
          name: "mock",
          platform_type: "mock",
          is_active: false,
          is_builtin: true,
        },
        {
          name: "my-reneryo",
          platform_type: "reneryo",
          is_active: true,
          is_builtin: false,
        },
      ],
      active_profile: "my-reneryo",
    };

    render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-dropdown"), {
      target: { value: "my-reneryo" },
    });

    await waitFor(() => {
      expect(mockGetProfile).toHaveBeenCalledWith("my-reneryo");
    });

    mockListProfiles.mockResolvedValue(updatedProfiles);

    fireEvent.click(screen.getByTestId("profile-switch-btn"));

    await waitFor(() => {
      expect(mockActivateProfile).toHaveBeenCalledWith("my-reneryo");
    });

    await waitFor(() => {
      expect(screen.getByText("Edit")).toBeTruthy();
    });
  });

  it("mock profile form fields are disabled", async () => {
    const { container } = render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      const platformSelect = findPlatformSelect(container);
      expect(platformSelect).not.toBeNull();
      expect(platformSelect!.disabled).toBe(true);
    });
  });

  it("does not call reset when confirmation is cancelled", async () => {
    vi.mocked(window.confirm).mockReturnValue(false);
    render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByText("Reset")).toBeTruthy();
    });

    fireEvent.click(screen.getByText("Reset"));

    expect(mockResetPlatformConfig).not.toHaveBeenCalled();
  });

  it("calls reset when confirmation is accepted", async () => {
    vi.mocked(window.confirm).mockReturnValue(true);
    render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByText("Reset")).toBeTruthy();
    });

    fireEvent.click(screen.getByText("Reset"));

    await waitFor(() => {
      expect(mockResetPlatformConfig).toHaveBeenCalledTimes(1);
    });
  });

  it("preserves none auth type when switching to a no-auth profile", async () => {
    render(<PlatformConfigSection onNotify={onNotify} />);

    await waitFor(() => {
      expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
    });

    fireEvent.change(screen.getByTestId("profile-dropdown"), {
      target: { value: "custom-no-auth" },
    });

    await waitFor(() => {
      expect(mockGetProfile).toHaveBeenCalledWith("custom-no-auth");
    });

    await waitFor(() => {
      const authSelect = screen.getByLabelText("Auth Type") as HTMLSelectElement;
      expect(authSelect.value).toBe("none");
    });
  });
});
