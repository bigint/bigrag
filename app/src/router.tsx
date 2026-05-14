import { createRouter } from "@tanstack/react-router";
import { AppErrorPage, AppNotFoundPage } from "@/components/status/status-page";
import { routeTree } from "./routeTree.gen";

export const router = createRouter({
  defaultErrorComponent: AppErrorPage,
  defaultNotFoundComponent: AppNotFoundPage,
  routeTree,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
