import { Switch } from "@/components/ui/switch";
import type { CollectionSearchMode } from "@/features/collections/collection-form-state";
import { cn } from "@/lib/cn";

const searchModeOptions: readonly { label: string; value: CollectionSearchMode }[] = [
  { value: "semantic", label: "Semantic" },
  { value: "keyword", label: "Keyword" },
  { value: "hybrid", label: "Hybrid" },
];

export const SearchModeControl = ({
  onChange,
  value,
}: {
  onChange: (value: CollectionSearchMode) => void;
  value: CollectionSearchMode;
}) => (
  <div className="flex shrink-0 flex-col gap-1.5">
    <span className="text-sm font-semibold">Mode</span>
    <div className="inline-grid grid-cols-3 gap-1 rounded-md border border-input bg-background p-1">
      {searchModeOptions.map((option) => {
        const active = option.value === value;
        return (
          <button
            aria-pressed={active}
            className={cn(
              "h-8 whitespace-nowrap rounded-sm px-4 text-sm font-semibold",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
              active
                ? "bg-primary text-primary-foreground"
                : "text-muted-foreground hover:text-foreground",
            )}
            key={option.value}
            onClick={() => onChange(option.value)}
            type="button"
          >
            {option.label}
          </button>
        );
      })}
    </div>
  </div>
);

export const SearchToggle = ({
  checked,
  label,
  onCheckedChange,
}: {
  checked: boolean;
  label: string;
  onCheckedChange: (checked: boolean) => void;
}) => (
  <div
    className={cn(
      "flex h-10 shrink-0 items-center gap-3 rounded-md border border-input bg-background px-3.5",
      checked && "border-primary bg-primary/5",
    )}
  >
    <span className="whitespace-nowrap text-sm font-semibold">{label}</span>
    <Switch aria-label={label} checked={checked} onCheckedChange={onCheckedChange} />
  </div>
);
