// @vitest-environment jsdom

/**
 * Tests for voice-widget-helpers — pure state-to-class mapping functions.
 *
 * Tests cover all DerivedState values and position variants to ensure
 * complete branch coverage of the helper module.
 */

import { describe, expect, it } from "vitest";

import {
  dotClasses,
  micAnimationClass,
  micColorClasses,
  micTooltip,
  panelPositionClasses,
  positionClasses,
  stateLabel,
} from "../voice-widget-helpers";

// ── positionClasses ────────────────────────────────────

describe("positionClasses", () => {
  it("returns bottom-right classes by default", () => {
    expect(positionClasses("bottom-right")).toContain("bottom-5");
    expect(positionClasses("bottom-right")).toContain("right-5");
  });

  it("returns bottom-left classes", () => {
    expect(positionClasses("bottom-left")).toContain("bottom-5");
    expect(positionClasses("bottom-left")).toContain("left-5");
  });

  it("returns top-right classes", () => {
    expect(positionClasses("top-right")).toContain("top-5");
    expect(positionClasses("top-right")).toContain("right-5");
  });

  it("returns top-left classes", () => {
    expect(positionClasses("top-left")).toContain("top-5");
    expect(positionClasses("top-left")).toContain("left-5");
  });
});

// ── panelPositionClasses ───────────────────────────────

describe("panelPositionClasses", () => {
  it("returns bottom-right panel anchor by default", () => {
    expect(panelPositionClasses("bottom-right")).toContain("bottom-16");
    expect(panelPositionClasses("bottom-right")).toContain("right-0");
  });

  it("returns top-left panel anchor", () => {
    expect(panelPositionClasses("top-left")).toContain("top-16");
    expect(panelPositionClasses("top-left")).toContain("left-0");
  });
});

// ── micColorClasses ────────────────────────────────────

describe("micColorClasses", () => {
  it("returns sky color for listening state", () => {
    expect(micColorClasses("listening")).toContain("bg-sky-500");
  });

  it("returns emerald color for speaking state", () => {
    expect(micColorClasses("speaking")).toContain("bg-emerald-500");
  });

  it("returns red color for error state", () => {
    expect(micColorClasses("error")).toContain("bg-red-500");
  });

  it("returns slate color for disconnected state", () => {
    expect(micColorClasses("disconnected")).toContain("bg-slate-400");
    expect(micColorClasses("disconnected")).toContain("cursor-not-allowed");
  });

  it("returns default idle classes for idle state", () => {
    expect(micColorClasses("idle")).toContain("bg-slate-200");
  });
});

// ── micAnimationClass ──────────────────────────────────

describe("micAnimationClass", () => {
  it("returns idle animation for idle state", () => {
    expect(micAnimationClass("idle")).toBe("voice-mic--idle");
  });

  it("returns listening animation for listening state", () => {
    expect(micAnimationClass("listening")).toBe("voice-mic--listening");
  });

  it("returns speaking animation for speaking state", () => {
    expect(micAnimationClass("speaking")).toBe("voice-mic--speaking");
  });

  it("returns empty string for processing state", () => {
    expect(micAnimationClass("processing")).toBe("");
  });

  it("returns empty string for disconnected state", () => {
    expect(micAnimationClass("disconnected")).toBe("");
  });
});

// ── dotClasses ─────────────────────────────────────────

describe("dotClasses", () => {
  it("returns active sky dot for listening", () => {
    expect(dotClasses("listening")).toContain("bg-sky-400");
    expect(dotClasses("listening")).toContain("voice-dot--active");
  });

  it("returns active amber dot for processing", () => {
    expect(dotClasses("processing")).toContain("bg-amber-400");
  });

  it("returns red dot for error", () => {
    expect(dotClasses("error")).toContain("bg-red-500");
  });

  it("returns slate dot for disconnected", () => {
    expect(dotClasses("disconnected")).toContain("bg-slate-400");
  });

  it("returns emerald dot for idle (default)", () => {
    expect(dotClasses("idle")).toContain("bg-emerald-500");
  });
});

// ── stateLabel ─────────────────────────────────────────

describe("stateLabel", () => {
  it("returns Ready for idle", () => {
    expect(stateLabel("idle")).toBe("Ready");
  });

  it("returns Listening… for listening", () => {
    expect(stateLabel("listening")).toBe("Listening…");
  });

  it("returns Processing… for processing", () => {
    expect(stateLabel("processing")).toBe("Processing…");
  });

  it("returns Speaking… for speaking", () => {
    expect(stateLabel("speaking")).toBe("Speaking…");
  });

  it("returns Error for error", () => {
    expect(stateLabel("error")).toBe("Error");
  });

  it("returns Voice unavailable for disconnected", () => {
    expect(stateLabel("disconnected")).toBe("Voice unavailable");
  });
});

// ── micTooltip ─────────────────────────────────────────

describe("micTooltip", () => {
  it("returns disconnected tooltip when disconnected", () => {
    expect(micTooltip("disconnected", "granted")).toContain("not connected");
  });

  it("returns denied tooltip when mic denied", () => {
    expect(micTooltip("idle", "denied")).toContain("Microphone blocked");
  });

  it("returns stop tooltip when listening", () => {
    expect(micTooltip("listening", "granted")).toContain("stop listening");
  });

  it("returns speak tooltip when idle and granted", () => {
    expect(micTooltip("idle", "granted")).toContain("Click to speak");
  });
});
