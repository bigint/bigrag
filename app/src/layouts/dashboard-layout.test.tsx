import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { DashboardLayout } from "./dashboard-layout";

const routeState = vi.hoisted(() => ({ pathname: "/vector-storage" }));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
  useRouterState: ({ select }: { select: (state: { location: { pathname: string } }) => string }) =>
    select({ location: routeState }),
}));

vi.mock("@/components/navigation/sidebar", () => ({
  MobileSidebar: () => null,
  Sidebar: () => <aside>Sidebar</aside>,
}));

vi.mock("@/hooks/use-auth", () => ({
  useSession: () => ({
    data: {
      user: {
        role: "admin",
      },
    },
    isError: false,
    isPending: false,
  }),
  useSetupStatus: () => ({
    data: {
      needs_setup: false,
    },
  }),
}));

describe("DashboardLayout", () => {
  it("keeps standard pages in a scroll area without reserving a bottom shell gutter", () => {
    routeState.pathname = "/vector-storage";

    const html = renderToStaticMarkup(
      <DashboardLayout>
        <div>Vector storage content</div>
      </DashboardLayout>,
    );

    expect(html).toContain("flex h-dvh overflow-hidden bg-background pt-2 pl-2");
    expect(html).not.toContain("bg-background py-2 pl-2");
    expect(html).toContain("relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden");
    expect(html).toContain(
      "min-h-0 flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10",
    );
  });
});
