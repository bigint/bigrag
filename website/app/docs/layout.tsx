import { DocsLayout } from "fumadocs-ui/layouts/docs";
import type { ReactNode } from "react";
import { baseOptions } from "@/lib/layout.shared";
import { source } from "@/lib/source";

const Layout = ({ children }: { children: ReactNode }) => (
  <DocsLayout
    sidebar={{
      defaultOpenLevel: 1,
    }}
    tree={source.getPageTree()}
    {...baseOptions()}
  >
    {children}
  </DocsLayout>
);

export default Layout;
