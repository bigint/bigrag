import { useQueryClient } from "@tanstack/react-query";
import { useNavigate, useRouterState } from "@tanstack/react-router";
import { Menu as MenuIcon } from "lucide-react";
import { useEffect, useState } from "react";
import { Logo } from "@/components/brand/logo";
import { MobileSidebar, Sidebar } from "@/components/navigation/sidebar";
import { ApiUnreachable } from "@/components/status/api-unreachable";
import { Page } from "@/components/ui/page";
import { Spinner } from "@/components/ui/spinner";
import { useInstanceSetupStatus } from "@/features/onboarding/use-instance-setup-status";
import { queryKeys } from "@/lib/query-keys";

const FULL_HEIGHT_ROUTES = ["/overview", "/chat"];

export const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useRouterState({ select: (state) => state.location });
  const pathname = location.pathname;
  const currentHref = location.href || pathname;
  const setup = useInstanceSetupStatus();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (pathname === "/login" || pathname === "/setup" || pathname === "/onboarding") return;
    if (setup.loading || setup.error) return;
    if (setup.needsAdminSetup) {
      navigate({ to: "/setup", replace: true });
      return;
    }
    if (!setup.session) {
      navigate({ to: "/login", search: { from: currentHref }, replace: true });
      return;
    }
    if (setup.requiresOnboarding && !setup.complete) {
      navigate({ to: "/onboarding", replace: true });
    }
  }, [
    currentHref,
    navigate,
    pathname,
    setup.complete,
    setup.error,
    setup.loading,
    setup.needsAdminSetup,
    setup.requiresOnboarding,
    setup.session,
  ]);

  if (setup.error) {
    return (
      <ApiUnreachable
        error={setup.error}
        onRetry={() => {
          queryClient.invalidateQueries({ queryKey: queryKeys.auth.all() });
          setup.refetch();
        }}
      />
    );
  }

  if (
    setup.loading ||
    setup.needsAdminSetup ||
    !setup.session ||
    (setup.requiresOnboarding && !setup.complete)
  ) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const isFullHeight = FULL_HEIGHT_ROUTES.some((r) => pathname.startsWith(r));
  const role = setup.session.user.role;

  return (
    <div className="flex h-dvh overflow-hidden bg-background pt-2 pl-2">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <Sidebar role={role} />
      <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} role={role} />
      <main id="main" className="relative flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden">
        <header className="flex shrink-0 items-center justify-between gap-2 border-b border-border bg-background px-3 py-2.5 lg:hidden">
          <button
            type="button"
            aria-label="Open navigation"
            onClick={() => setMobileNavOpen(true)}
            className="inline-flex size-9 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground"
          >
            <MenuIcon className="size-5" />
          </button>
          <Logo />
          <span className="size-9" aria-hidden />
        </header>
        {isFullHeight ? (
          children
        ) : (
          <div className="min-h-0 flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10">
            <Page.Container>{children}</Page.Container>
          </div>
        )}
      </main>
    </div>
  );
};
