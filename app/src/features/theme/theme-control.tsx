import { type LucideIcon, Monitor, Moon, Sun } from "lucide-react";
import { Tooltip } from "@/components/ui/tooltip";
import { cn } from "@/lib/cn";
import { type ThemeMode, useAdminTheme } from "./theme-provider";

const OPTIONS: readonly {
  mode: ThemeMode;
  label: string;
  icon: LucideIcon;
}[] = [
  { icon: Sun, label: "Light", mode: "light" },
  { icon: Moon, label: "Dark", mode: "dark" },
  { icon: Monitor, label: "System", mode: "system" },
];

export const ThemeControl = ({ className }: { className?: string }) => {
  const { mode, setMode } = useAdminTheme();

  return (
    <fieldset className={cn("inline-flex rounded-md border border-border bg-muted p-1", className)}>
      <legend className="sr-only">Theme</legend>
      {OPTIONS.map((option) => {
        const active = mode === option.mode;
        const Icon = option.icon;
        return (
          <Tooltip content={option.label} key={option.mode}>
            <button
              aria-label={option.label}
              aria-pressed={active}
              className={cn(
                "inline-flex size-8 items-center justify-center rounded-sm text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                active
                  ? "bg-background text-foreground shadow-sm"
                  : "hover:bg-accent hover:text-accent-foreground",
              )}
              onClick={() => setMode(option.mode)}
              type="button"
            >
              <Icon className="size-4" />
            </button>
          </Tooltip>
        );
      })}
    </fieldset>
  );
};
