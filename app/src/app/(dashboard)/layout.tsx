"use client";

import { Menu as MenuIcon } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { Logo } from "@/components/brand/logo";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { MobileSidebar, Sidebar } from "./components/sidebar";

const FULL_HEIGHT_ROUTES = ["/overview", "/playground"];

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const router = useRouter();
  const pathname = usePathname();
  const { data: setupStatus } = useSetupStatus();
  const { data: session, isPending, isError } = useSession();
  const [mobileNavOpen, setMobileNavOpen] = useState(false);

  useEffect(() => {
    if (isPending) return;
    if (session) return;
    if (setupStatus?.needs_setup) {
      router.replace("/setup");
      return;
    }
    if (isError || !session) {
      router.replace("/login");
    }
  }, [session, isPending, isError, setupStatus, router]);

  if (isPending || !session) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  const isFullHeight = FULL_HEIGHT_ROUTES.some((r) => pathname.startsWith(r));
  const role = session.user.role;

  return (
    <div className="flex h-dvh overflow-hidden bg-background p-2">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <Sidebar role={role} />
      <MobileSidebar open={mobileNavOpen} onClose={() => setMobileNavOpen(false)} role={role} />
      <main id="main" className="relative flex min-w-0 flex-1 flex-col overflow-hidden">
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
          <div className="flex-1 overflow-y-auto bg-background px-4 py-6 md:px-8 lg:px-10">
            <div className="mx-auto w-full max-w-7xl">{children}</div>
          </div>
        )}
      </main>
    </div>
  );
};

export default DashboardLayout;
