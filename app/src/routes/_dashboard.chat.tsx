import { createFileRoute } from "@tanstack/react-router";
import { lazy, Suspense } from "react";
import { Spinner } from "@/components/ui/spinner";

const ChatPage = lazy(async () => ({
  default: (await import("@/features/chat/chat-page")).ChatPage,
}));

const ChatRoute = () => (
  <Suspense
    fallback={
      <div className="flex justify-center py-12">
        <Spinner size="lg" />
      </div>
    }
  >
    <ChatPage />
  </Suspense>
);

export const Route = createFileRoute("/_dashboard/chat")({
  component: ChatRoute,
});
