import * as Select from "@radix-ui/react-select";

type BrandSelectOption = {
  value: string;
  label: string;
};

type BrandSelectProps = {
  value: string;
  onChange: (next: string) => void;
  placeholder?: string;
  options: BrandSelectOption[];
  className?: string;
};

export default function BrandSelect({
  value,
  onChange,
  placeholder = "Select option",
  options,
  className,
}: BrandSelectProps) {
  const NONE_VALUE = "__none__";
  const normalizedValue = value === "" ? undefined : value;

  return (
    <Select.Root
      value={normalizedValue}
      onValueChange={(next) => onChange(next === NONE_VALUE ? "" : next)}
    >
      <Select.Trigger
        className={
          className ??
          "mt-1 inline-flex w-full items-center justify-between rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 outline-none ring-sky-200 transition hover:border-sky-300 focus:ring-2 dark:border-slate-600 dark:bg-slate-900 dark:text-slate-100 dark:hover:border-sky-500/70"
        }
      >
        <Select.Value placeholder={placeholder} />
        <Select.Icon className="mr-2">
          <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor">
            <path d="M6 9l6 6 6-6" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
        </Select.Icon>
      </Select.Trigger>

      <Select.Portal>
        <Select.Content
          position="popper"
          sideOffset={6}
          className="z-[1200] overflow-hidden rounded-lg border border-slate-200 bg-white shadow-xl dark:border-slate-700 dark:bg-slate-900"
        >
          <Select.Viewport className="p-1">
            {options.map((option) => (
              <Select.Item
                key={option.value || NONE_VALUE}
                value={option.value === "" ? NONE_VALUE : option.value}
                className="relative flex cursor-pointer select-none items-center rounded-md px-8 py-2 text-sm text-slate-700 outline-none data-[highlighted]:bg-sky-100 data-[highlighted]:text-slate-900 dark:text-slate-200 dark:data-[highlighted]:bg-slate-800 dark:data-[highlighted]:text-slate-100"
              >
                <Select.ItemText>{option.label}</Select.ItemText>
                <Select.ItemIndicator className="absolute left-2 inline-flex items-center">
                  <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor">
                    <path d="M5 12l5 5L19 8" strokeWidth="2" strokeLinecap="round" />
                  </svg>
                </Select.ItemIndicator>
              </Select.Item>
            ))}
          </Select.Viewport>
        </Select.Content>
      </Select.Portal>
    </Select.Root>
  );
}
