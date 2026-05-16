import { createFileRoute } from "@tanstack/react-router";
import { AuditPage } from "@/features/audit/audit-page";

export const Route = createFileRoute("/_dashboard/audit")({
  component: () => <AuditPage />,
});
