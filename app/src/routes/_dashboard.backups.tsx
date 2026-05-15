import { createFileRoute } from "@tanstack/react-router";
import { BackupsPage } from "@/features/backups/backups-page";

export const Route = createFileRoute("/_dashboard/backups")({
  component: () => <BackupsPage />,
});
