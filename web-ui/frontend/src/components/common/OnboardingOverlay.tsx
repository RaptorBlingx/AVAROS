import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";

type OnboardingStep = {
  title: string;
  description: string;
  selector: string;
};

type OnboardingOverlayProps = {
  open: boolean;
  steps: readonly OnboardingStep[];
  onClose: () => void;
  onStepChange?: (stepIndex: number) => void;
};

type Box = {
  top: number;
  left: number;
  width: number;
  height: number;
};

function findVisibleTarget(selector: string): HTMLElement | null {
  const nodes = Array.from(
    document.querySelectorAll(selector),
  ) as HTMLElement[];
  return (
    nodes.find((node) => node.offsetWidth > 0 && node.offsetHeight > 0) ?? null
  );
}

export default function OnboardingOverlay({
  open,
  steps,
  onClose,
  onStepChange,
}: OnboardingOverlayProps) {
  const [stepIndex, setStepIndex] = useState(0);
  const [targetBox, setTargetBox] = useState<Box | null>(null);
  const initialScrollYRef = useRef<number | null>(null);

  const currentStep = steps[stepIndex] ?? null;

  useEffect(() => {
    if (open && initialScrollYRef.current === null) {
      initialScrollYRef.current = window.scrollY;
    }

    if (!open) {
      setStepIndex(0);
      setTargetBox(null);
      initialScrollYRef.current = null;
    }
  }, [open]);

  useEffect(() => {
    if (open) {
      onStepChange?.(stepIndex);
    }
  }, [onStepChange, open, stepIndex]);

  useEffect(() => {
    if (!open || !currentStep) {
      return;
    }

    const updateBox = () => {
      const target = findVisibleTarget(currentStep.selector);
      if (!target) {
        setTargetBox(null);
        return;
      }

      const rect = target.getBoundingClientRect();
      setTargetBox({
        top: rect.top,
        left: rect.left,
        width: rect.width,
        height: rect.height,
      });
    };

    const raf = window.requestAnimationFrame(updateBox);
    window.addEventListener("resize", updateBox);
    window.addEventListener("scroll", updateBox, { passive: true });
    return () => {
      window.cancelAnimationFrame(raf);
      window.removeEventListener("resize", updateBox);
      window.removeEventListener("scroll", updateBox);
    };
  }, [currentStep, open]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const target = currentStep ? findVisibleTarget(currentStep.selector) : null;
    if (!target) {
      return;
    }

    const rect = target.getBoundingClientRect();
    const topSafe = 90;
    const bottomSafe = window.innerHeight - 140;
    if (rect.top < topSafe) {
      const delta = rect.top - topSafe;
      window.scrollBy({ top: delta, behavior: "auto" });
      return;
    }
    if (rect.bottom > bottomSafe) {
      const delta = rect.bottom - bottomSafe;
      window.scrollBy({ top: delta, behavior: "auto" });
    }
  }, [currentStep, open]);

  const closeTour = useCallback(() => {
    const initialScrollY = initialScrollYRef.current;
    if (typeof initialScrollY === "number") {
      window.scrollTo({ top: initialScrollY, behavior: "auto" });
    }
    onClose();
    if (typeof initialScrollY === "number") {
      window.requestAnimationFrame(() => {
        window.scrollTo({ top: initialScrollY, behavior: "auto" });
      });
    }
  }, [onClose]);

  useEffect(() => {
    if (!open) {
      return;
    }
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        closeTour();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [closeTour, open]);

  const panelPosition = useMemo(() => {
    if (!targetBox) {
      return { top: "50%", left: "50%", transform: "translate(-50%, -50%)" };
    }

    const panelWidth = Math.min(window.innerWidth - 16, 340);
    const panelHeight = 190;
    const viewportPadding = 8;
    const preferredTop = targetBox.top + targetBox.height + 14;
    const fallbackTop = targetBox.top - panelHeight - 14;

    const unclampedTop =
      preferredTop + panelHeight <= window.innerHeight
        ? preferredTop
        : fallbackTop >= viewportPadding
        ? fallbackTop
        : window.innerHeight / 2 - panelHeight / 2;

    const targetCenterX = targetBox.left + targetBox.width / 2;
    const unclampedLeft = targetCenterX - panelWidth / 2;
    const clampedLeft = Math.min(
      window.innerWidth - panelWidth - viewportPadding,
      Math.max(viewportPadding, unclampedLeft),
    );
    const clampedTop = Math.min(
      window.innerHeight - panelHeight - viewportPadding,
      Math.max(viewportPadding, unclampedTop),
    );

    return {
      top: clampedTop,
      left: clampedLeft,
      transform: "none",
    };
  }, [targetBox]);

  if (!open || !currentStep) {
    return null;
  }

  const isLast = stepIndex === steps.length - 1;

  return createPortal(
    <div
      className="fixed inset-0 z-[1200]"
      role="dialog"
      aria-modal="true"
      aria-label="Onboarding tour"
    >
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-[1.5px]" />

      {targetBox && (
        <div
          className="pointer-events-none absolute rounded-xl border-2 border-cyan-300 shadow-[0_0_0_9999px_rgba(2,6,23,0.55)] dark:border-cyan-400"
          style={{
            top: targetBox.top - 6,
            left: targetBox.left - 6,
            width: targetBox.width + 12,
            height: targetBox.height + 12,
          }}
        />
      )}

      <div
        className="absolute w-[min(92vw,340px)] rounded-2xl border border-slate-200 bg-white p-4 shadow-2xl dark:border-slate-700 dark:bg-slate-900"
        style={panelPosition}
      >
        <p className="m-0 text-xs font-semibold uppercase tracking-[0.12em] text-sky-700 dark:text-sky-300">
          Onboarding {stepIndex + 1} / {steps.length}
        </p>
        <h3 className="m-0 mt-2 text-base font-semibold text-slate-900 dark:text-slate-100">
          {currentStep.title}
        </h3>
        <p className="m-0 mt-2 text-sm text-slate-600 dark:text-slate-300">
          {currentStep.description}
        </p>

        <div className="mt-4 flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={closeTour}
            className="btn-brand-subtle rounded-lg px-3 py-1.5 text-xs font-semibold"
          >
            Close Tour
          </button>
          <button
            type="button"
            onClick={() => {
              if (isLast) {
                closeTour();
                return;
              }
              setStepIndex((prev) => prev + 1);
            }}
            className="btn-brand-primary rounded-lg px-3 py-1.5 text-xs font-semibold"
          >
            {isLast ? "Got it!" : "Next"}
          </button>
        </div>
      </div>
    </div>,
    document.body,
  );
}
