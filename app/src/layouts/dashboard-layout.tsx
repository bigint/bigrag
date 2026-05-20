import { useQueryClient } from "@tanstack/react-query";
import { useRouterState } from "@tanstack/react-router";
import { Menu as MenuIcon } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/brand/logo";
import { MobileSidebar, Sidebar } from "@/components/navigation/sidebar";
import { ApiUnreachable } from "@/components/status/api-unreachable";
import { Page } from "@/components/ui/page";
import { Spinner } from "@/components/ui/spinner";
import { useAuthGate } from "@/features/auth/use-auth-gate";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { queryKeys } from "@/lib/query-keys";

const FULL_HEIGHT_ROUTES = ["/overview", "/chat"];

export const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const queryClient = useQueryClient();
  const location = useRouterState({ select: (state) => state.location });
  const pathname = location.pathname;
  const currentHref = location.href || pathname;
  const { error: setupError, isPending: setupPending } = useSetupStatus();
  const { data: session, error: sessionError, isPending } = useSession();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useAuthGate({ when: "setup-needed", to: "/setup" });
  useAuthGate({ when: "logged-out", to: "/login", search: { from: currentHref } });

  const authError = setupError ?? sessionError;
  if (authError && !session) {
    return (
      <ApiUnreachable
        error={authError}
        onRetry={() => {
          queryClient.invalidateQueries({ queryKey: queryKeys.auth.all() });
        }}
      />
    );
  }

  if (setupPending || isPending || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const isFullHeight = FULL_HEIGHT_ROUTES.some((r) => pathname.startsWith(r));
  const role = session.user.role;

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
