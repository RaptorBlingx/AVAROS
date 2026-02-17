// @vitest-environment jsdom

/**
 * ProfileSelector component tests.
 *
 * Verifies profile listing, switching, deletion (with confirm),
 * creation, and built-in profile protection.
 */

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// ── Mock API module (hoisted) ──────────────────────────

const mockApi = vi.hoisted(() => ({
  listProfiles: vi.fn(),
  getProfile: vi.fn(),
  activateProfile: vi.fn(),
  deleteProfile: vi.fn(),
  createProfile: vi.fn(),
  toFriendlyErrorMessage: vi.fn((e: unknown) =>
    e instanceof Error ? e.message : "Unknown error",
  ),
}));

// ── Mock ThemeProvider ─────────────────────────────────

vi.mock("../../../api/client", () => mockApi);

vi.mock("../../common/ThemeProvider", () => ({
  useTheme: () => ({ isDark: false }),
}));

// ── Import after mocks ────────────────────────────────

import ProfileSelector from "../ProfileSelector";

// ── Fixtures ───────────────────────────────────────────

const MOCK_PROFILE_LIST = {
  active_profile: "mock",
  profiles: [
    { name: "mock", platform_type: "mock", is_builtin: true, is_active: true },
    { name: "staging", platform_type: "reneryo", is_builtin: false, is_active: false },
  ],
};

const MOCK_PROFILE_DETAIL = {
  name: "mock",
  platform_type: "mock",
  api_url: "",
  api_key: "****",
  extra_settings: {},
  is_builtin: true,
  is_active: true,
};

// ── Helpers ────────────────────────────────────────────

function resetMocks(): void {
  mockApi.listProfiles.mockReset();
  mockApi.getProfile.mockReset();
  mockApi.activateProfile.mockReset();
  mockApi.deleteProfile.mockReset();
  mockApi.createProfile.mockReset();

  mockApi.listProfiles.mockResolvedValue(MOCK_PROFILE_LIST);
  mockApi.getProfile.mockResolvedValue(MOCK_PROFILE_DETAIL);
}

const noop = vi.fn();

function renderSelector(
  onNotify = noop,
  onProfileChange = noop,
) {
  return render(
    <ProfileSelector onNotify={onNotify} onProfileChange={onProfileChange} />,
  );
}

// ── Tests ──────────────────────────────────────────────

afterEach(() => {
  cleanup();
});

beforeEach(() => {
  resetMocks();
});

describe("ProfileSelector", () => {
  describe("rendering", () => {
    it("shows loading state initially", () => {
      // Never resolve the promise so it stays loading
      mockApi.listProfiles.mockReturnValue(new Promise(() => {}));
      renderSelector();
      expect(screen.getByTestId("profile-loading")).toBeTruthy();
    });

    it("renders profile dropdown with all profiles", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });
      const dropdown = screen.getByTestId("profile-dropdown") as HTMLSelectElement;
      expect(dropdown.options).toHaveLength(2);
      expect(dropdown.options[0].value).toBe("mock");
      expect(dropdown.options[1].value).toBe("staging");
    });

    it("shows mock profile first with Built-in label", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });
      const dropdown = screen.getByTestId("profile-dropdown") as HTMLSelectElement;
      expect(dropdown.options[0].textContent).toContain("Built-in");
    });

    it("shows active badge for active profile", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("active-badge")).toBeTruthy();
      });
    });

    it("shows builtin badge for mock profile", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("builtin-badge")).toBeTruthy();
      });
    });

    it("does not show delete button for mock profile", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });
      expect(screen.queryByTestId("delete-button")).toBeNull();
    });

    it("does not show switch button when active profile selected", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });
      expect(screen.queryByTestId("switch-button")).toBeNull();
    });
  });

  describe("profile switching", () => {
    it("shows switch button when non-active profile selected", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      const dropdown = screen.getByTestId("profile-dropdown");
      fireEvent.change(dropdown, { target: { value: "staging" } });

      expect(screen.getByTestId("switch-button")).toBeTruthy();
    });

    it("calls activateProfile on switch", async () => {
      mockApi.activateProfile.mockResolvedValue({
        status: "activated",
        active_profile: "staging",
        adapter_type: "reneryo",
        message: "Adapter reloaded successfully",
      });
      // After activation, list returns staging active
      const updatedList = {
        active_profile: "staging",
        profiles: [
          { name: "mock", platform_type: "mock", is_builtin: true, is_active: false },
          { name: "staging", platform_type: "reneryo", is_builtin: false, is_active: true },
        ],
      };

      const onNotify = vi.fn();
      renderSelector(onNotify);
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });

      mockApi.listProfiles.mockResolvedValue(updatedList);
      fireEvent.click(screen.getByTestId("switch-button"));

      await waitFor(() => {
        expect(mockApi.activateProfile).toHaveBeenCalledWith("staging");
      });
      await waitFor(() => {
        expect(onNotify).toHaveBeenCalledWith(
          "success",
          'Switched to profile "staging"',
        );
      });
    });

    it("shows error toast when switch fails", async () => {
      mockApi.activateProfile.mockRejectedValue(new Error("Connection refused"));

      const onNotify = vi.fn();
      renderSelector(onNotify);
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });
      fireEvent.click(screen.getByTestId("switch-button"));

      await waitFor(() => {
        expect(onNotify).toHaveBeenCalledWith("error", "Connection refused");
      });
    });
  });

  describe("profile deletion", () => {
    it("shows delete button for custom profiles", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });

      expect(screen.getByTestId("delete-button")).toBeTruthy();
    });

    it("requires confirmation before deleting", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });
      fireEvent.click(screen.getByTestId("delete-button"));

      expect(screen.getByTestId("confirm-delete-button")).toBeTruthy();
      expect(screen.getByTestId("cancel-delete-button")).toBeTruthy();
    });

    it("cancels deletion when cancel clicked", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });
      fireEvent.click(screen.getByTestId("delete-button"));
      fireEvent.click(screen.getByTestId("cancel-delete-button"));

      expect(screen.queryByTestId("confirm-delete-button")).toBeNull();
      expect(screen.getByTestId("delete-button")).toBeTruthy();
    });

    it("calls deleteProfile on confirm", async () => {
      mockApi.deleteProfile.mockResolvedValue({
        status: "deleted",
        deleted_profile: "staging",
        active_profile: "mock",
        message: "Profile deleted",
      });
      const onNotify = vi.fn();
      renderSelector(onNotify);
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });

      fireEvent.change(screen.getByTestId("profile-dropdown"), {
        target: { value: "staging" },
      });
      fireEvent.click(screen.getByTestId("delete-button"));
      fireEvent.click(screen.getByTestId("confirm-delete-button"));

      await waitFor(() => {
        expect(mockApi.deleteProfile).toHaveBeenCalledWith("staging");
      });
      await waitFor(() => {
        expect(onNotify).toHaveBeenCalledWith("success", "Profile deleted");
      });
    });
  });

  describe("profile creation", () => {
    it("shows new profile form when button clicked", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("new-profile-button")).toBeTruthy();
      });

      fireEvent.click(screen.getByTestId("new-profile-button"));
      expect(screen.getByTestId("new-profile-form")).toBeTruthy();
    });

    it("validates profile name format", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("new-profile-button")).toBeTruthy();
      });

      fireEvent.click(screen.getByTestId("new-profile-button"));
      const nameInput = screen.getByTestId("new-profile-name");
      fireEvent.change(nameInput, { target: { value: "A" } });
      fireEvent.click(screen.getByTestId("create-profile-button"));

      await waitFor(() => {
        expect(screen.getByTestId("name-error")).toBeTruthy();
      });
    });

    it("calls createProfile with valid name", async () => {
      mockApi.createProfile.mockResolvedValue({
        name: "my-profile",
        platform_type: "reneryo",
        api_url: "",
        api_key: "****",
        extra_settings: {},
        is_builtin: false,
        is_active: false,
      });
      const onNotify = vi.fn();
      renderSelector(onNotify);
      await waitFor(() => {
        expect(screen.getByTestId("new-profile-button")).toBeTruthy();
      });

      fireEvent.click(screen.getByTestId("new-profile-button"));
      fireEvent.change(screen.getByTestId("new-profile-name"), {
        target: { value: "my-profile" },
      });
      fireEvent.click(screen.getByTestId("create-profile-button"));

      await waitFor(() => {
        expect(mockApi.createProfile).toHaveBeenCalledWith({
          name: "my-profile",
          platform_type: "reneryo",
          api_url: "",
          api_key: "",
          extra_settings: {},
        });
      });
      await waitFor(() => {
        expect(onNotify).toHaveBeenCalledWith(
          "success",
          'Profile "my-profile" created',
        );
      });
    });

    it("shows error when creation fails", async () => {
      mockApi.createProfile.mockRejectedValue(
        new Error("Profile 'my-profile' already exists"),
      );
      const onNotify = vi.fn();
      renderSelector(onNotify);
      await waitFor(() => {
        expect(screen.getByTestId("new-profile-button")).toBeTruthy();
      });

      fireEvent.click(screen.getByTestId("new-profile-button"));
      fireEvent.change(screen.getByTestId("new-profile-name"), {
        target: { value: "my-profile" },
      });
      fireEvent.click(screen.getByTestId("create-profile-button"));

      await waitFor(() => {
        expect(screen.getByTestId("name-error")).toBeTruthy();
      });
    });
  });

  describe("mock profile protection", () => {
    it("cannot delete mock profile", async () => {
      renderSelector();
      await waitFor(() => {
        expect(screen.getByTestId("profile-dropdown")).toBeTruthy();
      });
      // Mock is selected by default
      expect(screen.queryByTestId("delete-button")).toBeNull();
    });
  });
});
