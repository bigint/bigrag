import { HomeLayout } from "fumadocs-ui/layouts/home";
import type { ReactNode } from "react";
import { baseOptions } from "@/lib/layout.shared";

const Layout = ({ children }: { children: ReactNode }) => (
  <HomeLayout {...baseOptions()}>{children}</HomeLayout>
);

export default Layout;
