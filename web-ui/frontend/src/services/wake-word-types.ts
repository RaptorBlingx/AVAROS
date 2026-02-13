/**
 * Types, configuration, and constants for the wake word service.
 */

// ── State ──────────────────────────────────────────────

export type WakeWordState =
  | "idle"
  | "loading"
  | "listening"
  | "detected"
  | "error"
  | "unsupported";

// ── Configuration ──────────────────────────────────────

export interface WakeWordConfig {
  /** Detection threshold, 0.0 – 1.0 (default 0.75). */
  sensitivity: number;
  /** Milliseconds to ignore subsequent detections after a hit (default 2000). */
  suppressionPeriod: number;
  /** URL to a custom transfer-learning model, or null for the built-in base. */
  modelUrl: string | null;
}

export const DEFAULT_CONFIG: WakeWordConfig = {
  sensitivity: 0.75,
  suppressionPeriod: 2000,
  modelUrl: null,
};

// ── Labels ─────────────────────────────────────────────

/** The label the transfer-learning model uses for the wake word. */
export const WAKE_WORD_LABEL = "hey avaros";

/** Fallback keyword from the base model for PoC use. */
export const BASE_MODEL_FALLBACK_LABEL = "_background_noise_";

// ── Callback types ─────────────────────────────────────

export type VoidCallback = () => void;
export type StateCallback = (state: WakeWordState) => void;
