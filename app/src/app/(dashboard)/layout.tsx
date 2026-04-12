"use client";

import { useRouter, usePathname } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { Sidebar } from "./components/sidebar";

// Routes that manage their own scrolling + padding (i.e. chat-style pages).
const FULL_HEIGHT_ROUTES = ["/playground"];

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const router = useRouter();
  const pathname = usePathname();
  const { data: setupStatus } = useSetupStatus();
  const { data: session, isPending, isError } = useSession();

  useEffect(() => {
    if (setupStatus?.needs_setup) {
      router.replace("/setup");
      return;
    }
    if (!isPending && (isError || !session)) {
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

  return (
    <div className="flex h-screen overflow-hidden">
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 focus:z-50 focus:rounded-md focus:bg-primary focus:px-3 focus:py-2 focus:text-primary-foreground"
      >
        Skip to main content
      </a>
      <Sidebar />
      <main id="main" className="flex min-w-0 flex-1 flex-col overflow-hidden">
        {isFullHeight ? (
          children
        ) : (
          <div className="flex-1 overflow-y-auto">
            <div className="mx-auto max-w-6xl px-6 py-8 md:px-10">{children}</div>
          </div>
        )}
      </main>
    </div>
  );
};

export default DashboardLayout;
