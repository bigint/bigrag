import { createFileRoute, Navigate } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/data-storage")({
  component: () => <Navigate replace search={{ tab: "storage" }} to="/settings" />,
});
