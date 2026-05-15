import { createFileRoute } from "@tanstack/react-router";
import { UsagePage } from "@/features/usage/usage-page";

export const Route = createFileRoute("/_dashboard/usage")({
  component: () => <UsagePage />,
});
