import {
  createContext,
  type ReactNode,
  useCallback,
  useContext,
  useEffect,
  useLayoutEffect,
  useMemo,
  useState,
} from "react";

export type ThemeMode = "light" | "dark" | "system";
type ResolvedTheme = "light" | "dark";

type ThemeContextValue = {
  mode: ThemeMode;
  resolvedTheme: ResolvedTheme;
  setMode: (mode: ThemeMode) => void;
};

const THEME_STORAGE_KEY = "bigrag:theme-mode";
const THEME_COLOR: Record<ResolvedTheme, string> = {
  dark: "#101112",
  light: "#ffffff",
};
const THEME_MODES = new Set<ThemeMode>(["light", "dark", "system"]);

const ThemeContext = createContext<ThemeContextValue | null>(null);

const isThemeMode = (value: string | null): value is ThemeMode =>
  Boolean(value && THEME_MODES.has(value as ThemeMode));

const readThemeMode = (): ThemeMode => {
  if (typeof window === "undefined") return "system";
  try {
    const value = window.localStorage.getItem(THEME_STORAGE_KEY);
    return isThemeMode(value) ? value : "system";
  } catch {
    return "system";
  }
};

const getSystemTheme = (): ResolvedTheme => {
  if (typeof window === "undefined") return "light";
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
};

const resolveTheme = (mode: ThemeMode): ResolvedTheme =>
  mode === "system" ? getSystemTheme() : mode;

const writeThemeMode = (mode: ThemeMode) => {
  if (typeof window === "undefined") return false;
  try {
    window.localStorage.setItem(THEME_STORAGE_KEY, mode);
    return true;
  } catch {
    return false;
  }
};

const applyTheme = (resolvedTheme: ResolvedTheme) => {
  if (typeof document === "undefined") return;
  const root = document.documentElement;
  root.dataset.theme = resolvedTheme;
  root.style.colorScheme = resolvedTheme;
  const themeColor = document.querySelector<HTMLMetaElement>('meta[name="theme-color"]');
  if (themeColor) themeColor.content = THEME_COLOR[resolvedTheme];
};

export const AdminThemeProvider = ({ children }: { children: ReactNode }) => {
  const [mode, setModeState] = useState<ThemeMode>(() => readThemeMode());
  const [resolvedTheme, setResolvedTheme] = useState<ResolvedTheme>(() => resolveTheme(mode));

  const setMode = useCallback((nextMode: ThemeMode) => {
    setModeState(nextMode);
    setResolvedTheme(resolveTheme(nextMode));
    writeThemeMode(nextMode);
  }, []);

  useLayoutEffect(() => {
    applyTheme(resolvedTheme);
  }, [resolvedTheme]);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const updateResolvedTheme = () => {
      setResolvedTheme(resolveTheme(mode));
    };
    updateResolvedTheme();
    if (mode !== "system") return;
    media.addEventListener("change", updateResolvedTheme);
    return () => media.removeEventListener("change", updateResolvedTheme);
  }, [mode]);

  useEffect(() => {
    const onStorage = (event: StorageEvent) => {
      if (event.key !== THEME_STORAGE_KEY) return;
      const nextMode = isThemeMode(event.newValue) ? event.newValue : "system";
      setModeState(nextMode);
      setResolvedTheme(resolveTheme(nextMode));
    };
    window.addEventListener("storage", onStorage);
    return () => window.removeEventListener("storage", onStorage);
  }, []);

  const value = useMemo(
    () => ({
      mode,
      resolvedTheme,
      setMode,
    }),
    [mode, resolvedTheme, setMode],
  );

  return <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>;
};

export const useAdminTheme = () => {
  const value = useContext(ThemeContext);
  if (!value) {
    throw new Error("useAdminTheme must be used within AdminThemeProvider");
  }
  return value;
};
