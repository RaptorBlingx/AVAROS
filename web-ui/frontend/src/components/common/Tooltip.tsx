import { useLayoutEffect, useRef, useState } from "react";
import type { ReactNode } from "react";

type TooltipProps = {
  content: string;
  ariaLabel: string;
  className?: string;
};

export default function Tooltip({ content, ariaLabel, className = "" }: TooltipProps) {
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const bubbleRef = useRef<HTMLSpanElement | null>(null);
  const [isOpen, setIsOpen] = useState(false);
  const [leftOffset, setLeftOffset] = useState(0);

  useLayoutEffect(() => {
    if (!isOpen || !wrapperRef.current || !bubbleRef.current) {
      return;
    }

    const wrapperRect = wrapperRef.current.getBoundingClientRect();
    const bubbleRect = bubbleRef.current.getBoundingClientRect();

    const centeredLeft = wrapperRect.width / 2 - bubbleRect.width / 2;
    const absoluteLeft = wrapperRect.left + centeredLeft;
    const minLeft = 8;
    const maxLeft = window.innerWidth - bubbleRect.width - 8;
    const clampedAbsoluteLeft = Math.min(maxLeft, Math.max(minLeft, absoluteLeft));
    setLeftOffset(clampedAbsoluteLeft - wrapperRect.left);
  }, [isOpen]);

  useLayoutEffect(() => {
    if (!isOpen) {
      setLeftOffset(0);
    }
  }, [isOpen]);

  return (
    <span
      ref={wrapperRef}
      className={`relative inline-flex items-center ${className}`}
      onMouseEnter={() => setIsOpen(true)}
      onMouseLeave={() => setIsOpen(false)}
    >
      <button
        type="button"
        aria-label={ariaLabel}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-300 bg-white text-[11px] font-semibold text-slate-600 transition hover:border-sky-300 hover:text-sky-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400/70 dark:border-slate-500 dark:bg-slate-900 dark:text-slate-200 dark:hover:border-cyan-400 dark:hover:text-cyan-300"
        onFocus={() => setIsOpen(true)}
        onBlur={() => setIsOpen(false)}
      >
        ?
      </button>
      {isOpen && (
        <span
          ref={bubbleRef}
          role="tooltip"
          className="pointer-events-none absolute bottom-full z-50 mb-2 w-64 max-w-[calc(100vw-1rem)] whitespace-normal break-words rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs leading-5 text-slate-700 shadow-lg dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100"
          style={{ left: leftOffset }}
        >
          {content}
        </span>
      )}
    </span>
  );
}
