import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/chat")({
  component: lazyRouteComponent(() =>
    import("@/features/chat/chat-page").then((m) => ({ default: m.ChatPage })),
  ),
});
