/**
 * Pure helper functions for wake word spectrogram analysis.
 *
 * Extracted from WakeWordService to keep file sizes under 300 lines.
 */

import { WAKE_WORD_LABEL, BASE_MODEL_FALLBACK_LABEL } from "./wake-word-types";

// ── Types ──────────────────────────────────────────────

/** Result of finding the highest-scoring label in a spectrogram. */
export interface TopScoreResult {
  label: string;
  score: number;
}

// ── Functions ──────────────────────────────────────────

/**
 * Find the label with the highest confidence score.
 *
 * @param scores - Float32Array of per-label scores from the model.
 * @param labels - Word labels corresponding to each score index.
 * @returns The top-scoring label and its confidence, or null if empty.
 */
export function findTopScore(
  scores: Float32Array,
  labels: string[],
): TopScoreResult | null {
  if (labels.length === 0 || scores.length === 0) return null;

  let maxIdx = 0;
  let maxScore = scores[0];
  for (let i = 1; i < scores.length; i++) {
    if (scores[i] > maxScore) {
      maxScore = scores[i];
      maxIdx = i;
    }
  }

  return { label: labels[maxIdx], score: maxScore };
}

/**
 * Check whether a label matches the wake word.
 *
 * In transfer-model mode, the label must match the custom word.
 * In base-model mode, any non-background keyword is accepted
 * as a proof-of-concept stand-in.
 *
 * @param label              - The detected label string.
 * @param usingTransferModel - Whether a custom model is active.
 */
export function isWakeWordLabel(
  label: string,
  usingTransferModel: boolean,
): boolean {
  if (usingTransferModel) {
    return label.toLowerCase() === WAKE_WORD_LABEL;
  }
  return (
    label !== BASE_MODEL_FALLBACK_LABEL &&
    label !== "_unknown_" &&
    label !== "background_noise"
  );
}

/**
 * Check whether we are inside the suppression window.
 *
 * @param lastDetection     - Timestamp (ms) of the last detection.
 * @param suppressionPeriod - Duration (ms) of the suppression window.
 */
export function isSuppressionActive(
  lastDetection: number,
  suppressionPeriod: number,
): boolean {
  return Date.now() - lastDetection < suppressionPeriod;
}
