import { createFileRoute, Navigate } from "@tanstack/react-router";

export const Route = createFileRoute("/_dashboard/backups")({
  component: () => <Navigate replace search={{ tab: "backups" }} to="/settings" />,
});
