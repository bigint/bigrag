"use client";

import { useCallback, useEffect, useState } from "react";

type Theme = "light" | "dark" | "system";

const STORAGE_KEY = "bigrag:theme";

function applyTheme(theme: Theme) {
  const root = document.documentElement;
  const resolved =
    theme === "system"
      ? window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light"
      : theme;
  root.classList.toggle("dark", resolved === "dark");
}

export function useTheme() {
  const [theme, setThemeState] = useState<Theme>("system");

  useEffect(() => {
    const stored = (localStorage.getItem(STORAGE_KEY) as Theme | null) ?? "system";
    setThemeState(stored);
    applyTheme(stored);

    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      if ((localStorage.getItem(STORAGE_KEY) as Theme) === "system") {
        applyTheme("system");
      }
    };
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);

  const setTheme = useCallback((next: Theme) => {
    localStorage.setItem(STORAGE_KEY, next);
    setThemeState(next);
    applyTheme(next);
  }, []);

  return { theme, setTheme };
}
