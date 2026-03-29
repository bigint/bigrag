import { AppShell } from "@/components/app-shell";

const DashboardLayout = ({ children }: { readonly children: React.ReactNode }) => (
  <AppShell>{children}</AppShell>
);

export default DashboardLayout;
