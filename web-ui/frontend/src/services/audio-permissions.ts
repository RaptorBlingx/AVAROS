/**
 * Microphone permission helpers for the Web Speech API.
 *
 * Manages microphone access state and browser capability detection.
 * Uses navigator.permissions and navigator.mediaDevices APIs.
 */

// ── Types ──────────────────────────────────────────────

export type PermissionState = "prompt" | "granted" | "denied" | "unsupported";

// ── Functions ──────────────────────────────────────────

/**
 * Request microphone permission from the browser.
 *
 * Triggers the browser permission dialog if the user hasn't decided yet.
 * On success the media stream is released immediately — the Web Speech API
 * handles its own audio capture.
 *
 * @returns The resulting permission state.
 */
export async function requestMicrophonePermission(): Promise<PermissionState> {
  if (typeof navigator === "undefined" || !navigator.mediaDevices) {
    return "unsupported";
  }

  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    // Release the stream — we only needed it to trigger the permission dialog
    for (const track of stream.getTracks()) {
      track.stop();
    }
    return "granted";
  } catch (err) {
    if (err instanceof DOMException) {
      if (
        err.name === "NotAllowedError" ||
        err.name === "PermissionDeniedError"
      ) {
        return "denied";
      }
      if (err.name === "NotFoundError") {
        // No microphone hardware
        return "unsupported";
      }
    }
    return "denied";
  }
}

/**
 * Check the current microphone permission without triggering a dialog.
 *
 * Falls back to "prompt" when the Permissions API is unavailable.
 *
 * @returns The current permission state.
 */
export async function checkMicrophonePermission(): Promise<PermissionState> {
  if (typeof navigator === "undefined") return "unsupported";

  // Permissions API may not exist in all browsers
  if (navigator.permissions) {
    try {
      const result = await navigator.permissions.query({
        name: "microphone" as PermissionName,
      });
      switch (result.state) {
        case "granted":
          return "granted";
        case "denied":
          return "denied";
        default:
          return "prompt";
      }
    } catch {
      // Permissions API doesn't support "microphone" query in some browsers
      return "prompt";
    }
  }

  return "prompt";
}

/**
 * Check whether the SpeechRecognition API is available.
 */
export function isSpeechRecognitionSupported(): boolean {
  if (typeof window === "undefined") return false;
  return (
    "SpeechRecognition" in window || "webkitSpeechRecognition" in window
  );
}

/**
 * Check whether the speechSynthesis API is available.
 */
export function isSpeechSynthesisSupported(): boolean {
  if (typeof window === "undefined") return false;
  return "speechSynthesis" in window;
}
