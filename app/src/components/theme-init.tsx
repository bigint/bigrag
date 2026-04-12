"use client";

import { useEffect } from "react";

const applyStoredTheme = () => {
  try {
    const raw = localStorage.getItem("bigrag-theme");
    let theme: "light" | "dark" | "system" = "system";
    if (raw) {
      const parsed = JSON.parse(raw) as { state?: { theme?: string } };
      if (parsed?.state?.theme === "light" || parsed?.state?.theme === "dark") {
        theme = parsed.state.theme;
      }
    }
    const resolved =
      theme === "system"
        ? window.matchMedia("(prefers-color-scheme: dark)").matches
          ? "dark"
          : "light"
        : theme;
    document.documentElement.classList.toggle("dark", resolved === "dark");
  } catch {
    // ignore — stay on default
  }
};

applyStoredTheme();

export const ThemeInit = () => {
  useEffect(() => {
    applyStoredTheme();
    const mq = window.matchMedia("(prefers-color-scheme: dark)");
    const handler = () => applyStoredTheme();
    mq.addEventListener("change", handler);
    return () => mq.removeEventListener("change", handler);
  }, []);
  return null;
};
