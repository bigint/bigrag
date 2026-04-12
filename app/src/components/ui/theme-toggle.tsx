"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTheme } from "@/hooks/use-theme";

const ORDER: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];

export const ThemeToggle = () => {
  const { theme, setTheme } = useTheme();

  const onClick = () => {
    const next = ORDER[(ORDER.indexOf(theme as (typeof ORDER)[number]) + 1) % ORDER.length];
    setTheme(next);
  };

  const label =
    theme === "light" ? "Switch to dark theme" :
    theme === "dark" ? "Switch to system theme" :
    "Switch to light theme";

  const icon =
    theme === "light" ? <Sun aria-hidden className="size-4" /> :
    theme === "dark" ? <Moon aria-hidden className="size-4" /> :
    <Monitor aria-hidden className="size-4" />;

  return (
    <Button
      aria-label={label}
      title={label}
      onClick={onClick}
      size="sm"
      variant="ghost"
    >
      {icon}
    </Button>
  );
};
