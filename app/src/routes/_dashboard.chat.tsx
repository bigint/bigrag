import { createFileRoute } from "@tanstack/react-router";
import { ChatPage } from "@/features/chat/chat-page";

export const Route = createFileRoute("/_dashboard/chat")({
  component: () => <ChatPage />,
});
