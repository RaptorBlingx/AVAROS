/**
 * Pure helper functions for VoiceWidget visual state mapping.
 *
 * Extracted from VoiceWidget.tsx to keep file sizes under 300 lines.
 * All functions are stateless — they map derived state to class strings or labels.
 */

import type { VoiceState } from "../../contexts/voice-types";

// ── Types ──────────────────────────────────────────────

export type WidgetPosition =
  | "bottom-right"
  | "bottom-left"
  | "top-right"
  | "top-left";

/** UI-level state that adds "disconnected" to the voice engine states. */
export type DerivedState = VoiceState | "disconnected";

// ── Position helpers ───────────────────────────────────

/** Map position prop to Tailwind positioning classes. */
export function positionClasses(position: WidgetPosition): string {
  switch (position) {
    case "bottom-left":
      return "bottom-5 left-5";
    case "top-right":
      return "top-5 right-5";
    case "top-left":
      return "top-5 left-5";
    default:
      return "bottom-5 right-5";
  }
}

/** Map panel anchor relative to button per position. */
export function panelPositionClasses(position: WidgetPosition): string {
  switch (position) {
    case "bottom-left":
      return "bottom-16 left-0";
    case "top-right":
      return "top-16 right-0";
    case "top-left":
      return "top-16 left-0";
    default:
      return "bottom-16 right-0";
  }
}

// ── State-to-class helpers ─────────────────────────────

/** Map derived state to mic button Tailwind classes. */
export function micColorClasses(state: DerivedState): string {
  switch (state) {
    case "listening":
      return "bg-sky-500 text-white shadow-lg shadow-sky-500/30";
    case "processing":
      return "bg-sky-500 text-white opacity-80";
    case "speaking":
      return "bg-emerald-500 text-white shadow-lg shadow-emerald-500/30";
    case "error":
      return "bg-red-500 text-white";
    case "disconnected":
      return "bg-slate-400 text-white cursor-not-allowed dark:bg-slate-600";
    default:
      return "bg-slate-200 text-slate-600 hover:bg-slate-300 dark:bg-slate-700 dark:text-slate-300 dark:hover:bg-slate-600";
  }
}

/** Map derived state to CSS animation class on the mic button. */
export function micAnimationClass(state: DerivedState): string {
  switch (state) {
    case "idle":
      return "voice-mic--idle";
    case "listening":
      return "voice-mic--listening";
    case "speaking":
      return "voice-mic--speaking";
    default:
      return "";
  }
}

/** Map derived state to status-dot color classes. */
export function dotClasses(state: DerivedState): string {
  switch (state) {
    case "listening":
      return "bg-sky-400 voice-dot--active";
    case "processing":
      return "bg-amber-400 voice-dot--active";
    case "speaking":
      return "bg-emerald-400 voice-dot--active";
    case "error":
      return "bg-red-500";
    case "disconnected":
      return "bg-slate-400";
    default:
      return "bg-emerald-500";
  }
}

/** Human-readable label for the current state. */
export function stateLabel(state: DerivedState): string {
  switch (state) {
    case "idle":
      return "Ready";
    case "listening":
      return "Listening…";
    case "processing":
      return "Processing…";
    case "speaking":
      return "Speaking…";
    case "error":
      return "Error";
    case "disconnected":
      return "Voice unavailable";
  }
}

/** Tooltip text for the mic button. */
export function micTooltip(
  state: DerivedState,
  micPermission: string,
): string {
  if (state === "disconnected") return "Voice unavailable — not connected";
  if (micPermission === "denied")
    return "Microphone blocked. Enable in browser settings.";
  if (state === "listening") return "Click to stop listening";
  return "Click to speak";
}
