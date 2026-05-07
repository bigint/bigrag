import { createFileRoute, Outlet } from "@tanstack/react-router";
import { AuthLayout } from "@/layouts/auth-layout";

export const Route = createFileRoute("/_auth")({
  component: () => <AuthRoute />,
});

const AuthRoute = () => (
  <AuthLayout>
    <Outlet />
  </AuthLayout>
);
