import { useCallback, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export type ToastItem = {
  id: number;
  type: "success" | "error";
  message: string;
};

type ToastProps = {
  toasts: ToastItem[];
  onDismiss: (id: number) => void;
};

export default function Toast({ toasts, onDismiss }: ToastProps) {
  const autoDismissTimers = useRef<Map<number, number>>(new Map());
  const clickDismissTimers = useRef<Map<number, number>>(new Map());
  const closingIdsRef = useRef<Set<number>>(new Set());
  const [closingIds, setClosingIds] = useState<Set<number>>(new Set());

  const closeWithAnimation = useCallback(
    (id: number) => {
      if (clickDismissTimers.current.has(id)) {
        return;
      }
      if (closingIdsRef.current.has(id)) {
        return;
      }
      closingIdsRef.current.add(id);
      setClosingIds(new Set(closingIdsRef.current));
      const timer = window.setTimeout(() => {
        onDismiss(id);
        closingIdsRef.current.delete(id);
        setClosingIds(new Set(closingIdsRef.current));
        clickDismissTimers.current.delete(id);
      }, 220);
      clickDismissTimers.current.set(id, timer);
    },
    [onDismiss],
  );

  useEffect(() => {
    const activeIds = new Set(toasts.map((toast) => toast.id));

    for (const toast of toasts) {
      if (!autoDismissTimers.current.has(toast.id)) {
        const timer = window.setTimeout(() => {
          closeWithAnimation(toast.id);
          autoDismissTimers.current.delete(toast.id);
        }, 3000);
        autoDismissTimers.current.set(toast.id, timer);
      }
    }

    for (const [id, timer] of autoDismissTimers.current) {
      if (!activeIds.has(id)) {
        window.clearTimeout(timer);
        autoDismissTimers.current.delete(id);
      }
    }

  }, [closeWithAnimation, toasts]);

  useEffect(() => {
    const activeIds = new Set(toasts.map((toast) => toast.id));
    const next = new Set<number>();
    for (const id of closingIdsRef.current) {
      if (activeIds.has(id)) {
        next.add(id);
      }
    }
    closingIdsRef.current = next;
    setClosingIds(new Set(next));
  }, [toasts]);

  useEffect(() => {
    return () => {
      for (const [, timer] of autoDismissTimers.current) {
        window.clearTimeout(timer);
      }
      autoDismissTimers.current.clear();
      for (const [, timer] of clickDismissTimers.current) {
        window.clearTimeout(timer);
      }
      clickDismissTimers.current.clear();
    };
  }, []);

  return createPortal(
    <div className="pointer-events-none fixed bottom-4 right-4 z-[1000] space-y-2">
      {toasts.map((toast) => (
        <div
          key={toast.id}
          onClick={() => closeWithAnimation(toast.id)}
          className={`toast-item pointer-events-auto w-[min(92vw,340px)] cursor-pointer rounded-lg border px-4 py-3 text-sm shadow-lg ${
            closingIds.has(toast.id) ? "toast-item--closing" : ""
          } ${
            toast.type === "success"
              ? "border-emerald-300 bg-emerald-50 text-emerald-900"
              : "border-rose-300 bg-rose-50 text-rose-900"
          }`}
        >
          <div className="flex items-center justify-between gap-3">
            <p className="m-0">{toast.message}</p>
          </div>
        </div>
      ))}
    </div>,
    document.body,
  );
}
