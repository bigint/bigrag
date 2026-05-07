import { createFileRoute, Outlet } from "@tanstack/react-router";
import { DashboardLayout } from "@/layouts/dashboard-layout";

export const Route = createFileRoute("/_dashboard")({
  component: () => <DashboardRoute />,
});

const DashboardRoute = () => (
  <DashboardLayout>
    <Outlet />
  </DashboardLayout>
);
