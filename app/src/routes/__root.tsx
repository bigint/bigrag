import { createRootRoute, Outlet } from "@tanstack/react-router";
import { type ComponentType, useEffect, useState } from "react";
import "@fontsource-variable/outfit";
import { Providers } from "@/providers";
import "@/styles/globals.css";

export const Route = createRootRoute({
  component: () => <RootLayout />,
});

type DevtoolsComponent = ComponentType<{ position?: "bottom-left" }>;

const useDevtools = (): DevtoolsComponent | null => {
  const [Devtools, setDevtools] = useState<DevtoolsComponent | null>(null);
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    if (import.meta.env.VITE_SHOW_ROUTER_DEVTOOLS !== "true") return;
    let cancelled = false;
    void import("@tanstack/react-router-devtools").then((mod) => {
      if (!cancelled) setDevtools(() => mod.TanStackRouterDevtools);
    });
    return () => {
      cancelled = true;
    };
  }, []);
  return Devtools;
};

const RootLayout = () => {
  const Devtools = useDevtools();
  return (
    <Providers>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground"
      >
        Skip to content
      </a>
      <Outlet />
      {Devtools && <Devtools position="bottom-left" />}
    </Providers>
  );
};
