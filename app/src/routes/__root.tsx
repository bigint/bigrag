import { createRootRoute, Outlet } from "@tanstack/react-router";
import { TanStackRouterDevtools } from "@tanstack/react-router-devtools";
import "@fontsource-variable/outfit";
import { Providers } from "@/providers";
import "@/styles/globals.css";

export const Route = createRootRoute({
  component: () => <RootLayout />,
});

const RootLayout = () => (
  <Providers>
    <a
      href="#main"
      className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground"
    >
      Skip to content
    </a>
    <Outlet />
    {import.meta.env.VITE_SHOW_ROUTER_DEVTOOLS === "true" && (
      <TanStackRouterDevtools position="bottom-left" />
    )}
  </Providers>
);
