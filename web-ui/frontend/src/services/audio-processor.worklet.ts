/**
 * AudioWorklet processor — resamples browser audio to 16 kHz int16 PCM.
 *
 * Browser microphones typically output 44100 or 48000 Hz float32 samples.
 * The openWakeWord backend expects 16 kHz signed-16-bit-LE PCM in 80 ms
 * frames (1280 samples = 2560 bytes).
 *
 * This processor accumulates resampled samples and posts complete frames
 * back to the main thread via `port.postMessage`.
 *
 * Usage (main thread):
 *   await audioContext.audioWorklet.addModule("audio-processor.worklet.js");
 *   const node = new AudioWorkletNode(ctx, "pcm-resampler");
 *   source.connect(node);
 *   node.port.onmessage = (e) => ws.send(e.data); // ArrayBuffer
 */

// ── AudioWorklet global types (not in standard TS lib) ─

/* eslint-disable no-var */
declare class AudioWorkletProcessor {
  readonly port: MessagePort;
  process(
    inputs: Float32Array[][],
    outputs: Float32Array[][],
    parameters: Record<string, Float32Array>,
  ): boolean;
}

declare function registerProcessor(
  name: string,
  ctor: new () => AudioWorkletProcessor,
): void;

declare var sampleRate: number;
/* eslint-enable no-var */

// ── Constants ──────────────────────────────────────────

/** Target sample rate expected by openWakeWord. */
const TARGET_SAMPLE_RATE = 16_000;

/**
 * Samples per output frame (80 ms at 16 kHz).
 * Matches `SAMPLES_PER_FRAME` in the Python backend.
 */
const SAMPLES_PER_FRAME = 1280;

// ── Processor ──────────────────────────────────────────

class PCMResamplerProcessor extends AudioWorkletProcessor {
  /**
   * Accumulates resampled int16 samples until a full frame is ready.
   * Stored as raw bytes for zero-copy transfer.
   */
  private buffer: Int16Array = new Int16Array(SAMPLES_PER_FRAME);
  private bufferOffset = 0;

  /** Fractional position in the source buffer for linear interpolation. */
  private resampleRatio = 1;

  constructor() {
    super();
    // sampleRate is a global in AudioWorkletGlobalScope
    this.resampleRatio = sampleRate / TARGET_SAMPLE_RATE;
  }

  /**
   * Process 128-sample render quanta from the browser audio graph.
   *
   * Resamples float32 → 16 kHz int16 using linear interpolation,
   * buffers output, and posts complete 2560-byte frames.
   *
   * @returns `true` to keep the processor alive.
   */
  process(inputs: Float32Array[][]): boolean {
    const input = inputs[0];
    if (!input || input.length === 0) return true;

    const channelData = input[0];
    if (!channelData || channelData.length === 0) return true;

    this.resampleAndBuffer(channelData);
    return true;
  }

  // ── Resampling ─────────────────────────────────────

  /**
   * Downsample float32 input to 16 kHz int16 via linear interpolation.
   *
   * Walks through the source at `resampleRatio` steps, linearly
   * interpolating between adjacent samples for smooth conversion.
   * Clamps output to int16 range (−32768 … 32767).
   */
  private resampleAndBuffer(source: Float32Array): void {
    const ratio = this.resampleRatio;
    const srcLen = source.length;

    // Number of output samples we can produce from this input
    const outputCount = Math.floor(srcLen / ratio);

    for (let i = 0; i < outputCount; i++) {
      const srcIndex = i * ratio;
      const idx = Math.floor(srcIndex);
      const frac = srcIndex - idx;

      // Linear interpolation between two source samples
      const s0 = source[idx] ?? 0;
      const s1 = source[Math.min(idx + 1, srcLen - 1)] ?? 0;
      const interpolated = s0 + frac * (s1 - s0);

      // Convert float32 (−1.0 … 1.0) → int16 (−32768 … 32767)
      const clamped = Math.max(-1, Math.min(1, interpolated));
      this.buffer[this.bufferOffset++] = Math.round(clamped * 32767);

      // Post complete frame and reset buffer
      if (this.bufferOffset >= SAMPLES_PER_FRAME) {
        this.postFrame();
      }
    }
  }

  /**
   * Post a complete 2560-byte PCM frame to the main thread.
   *
   * Creates a copy of the buffer so the original can be reused.
   * Resets the buffer offset for the next frame.
   */
  private postFrame(): void {
    const frame = this.buffer.slice(0, SAMPLES_PER_FRAME);
    this.port.postMessage(frame.buffer, [frame.buffer]);
    this.buffer = new Int16Array(SAMPLES_PER_FRAME);
    this.bufferOffset = 0;
  }
}

registerProcessor("pcm-resampler", PCMResamplerProcessor);
