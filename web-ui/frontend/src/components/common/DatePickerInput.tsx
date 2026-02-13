import { useEffect, useMemo, useState } from "react";
import * as Popover from "@radix-ui/react-popover";
import { DayPicker } from "react-day-picker";
import type { Matcher } from "react-day-picker";
import { format, parseISO } from "date-fns";
import "react-day-picker/dist/style.css";

type DatePickerInputProps = {
  id?: string;
  value: string;
  onChange: (next: string) => void;
  max?: string;
  min?: string;
  className?: string;
  buttonClassName?: string;
};

function toDate(value: string): Date | undefined {
  if (!value) return undefined;
  try {
    return parseISO(`${value}T00:00:00`);
  } catch {
    return undefined;
  }
}

function toIsoDate(date?: Date): string {
  if (!date) return "";
  return format(date, "yyyy-MM-dd");
}

function toDisplayDate(value: string): string {
  const parsed = toDate(value);
  if (!parsed) {
    return "";
  }
  return format(parsed, "PPP");
}

export default function DatePickerInput({
  id,
  value,
  onChange,
  max,
  min,
  className,
  buttonClassName,
}: DatePickerInputProps) {
  const [open, setOpen] = useState(false);
  const now = useMemo(() => new Date(), []);
  const selected = useMemo(() => toDate(value), [value]);
  const [month, setMonth] = useState<Date>(selected ?? now);
  const minDate = useMemo(() => toDate(min ?? ""), [min]);
  const maxDate = useMemo(() => toDate(max ?? ""), [max]);
  const disabledMatchers = useMemo<Matcher[]>(() => {
    const matchers: Matcher[] = [];
    if (minDate) {
      matchers.push({ before: minDate });
    }
    if (maxDate) {
      matchers.push({ after: maxDate });
    }
    return matchers;
  }, [minDate, maxDate]);
  const displayValue = useMemo(() => toDisplayDate(value), [value]);

  useEffect(() => {
    if (!open) {
      return;
    }
    setMonth(selected ?? now);
  }, [open, selected, now]);

  return (
    <Popover.Root open={open} onOpenChange={setOpen}>
      <Popover.Trigger asChild>
        <button
          id={id}
          type="button"
          className={
            buttonClassName ??
            "mt-1 inline-flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-left text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
          }
          aria-label="Pick date"
        >
          <span className={displayValue ? "" : "text-slate-500 dark:text-slate-400"}>
            {displayValue || "Pick a date"}
          </span>
          <svg viewBox="0 0 24 24" className="h-4 w-4 opacity-70" fill="none" stroke="currentColor">
            <path d="M6 9l6 6 6-6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </button>
      </Popover.Trigger>

      <Popover.Portal>
        <Popover.Content
          sideOffset={8}
          align="start"
          onOpenAutoFocus={(event) => event.preventDefault()}
          onCloseAutoFocus={(event) => event.preventDefault()}
          className={`z-[1200] rounded-xl border border-slate-200 bg-white p-3 shadow-xl dark:border-slate-700 dark:bg-slate-900 ${className ?? ""}`}
        >
          <DayPicker
            mode="single"
            selected={selected}
            month={month}
            onMonthChange={setMonth}
            captionLayout="dropdown"
            navLayout="around"
            startMonth={new Date(2000, 0)}
            endMonth={new Date(now.getFullYear(), now.getMonth())}
            onSelect={(date) => {
              onChange(toIsoDate(date));
              setOpen(false);
            }}
            showOutsideDays
            disabled={disabledMatchers}
            className="rdp-avaros"
          />
        </Popover.Content>
      </Popover.Portal>
    </Popover.Root>
  );
}
