"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { Sidebar } from "./components/sidebar";

const DashboardLayout = ({ children }: { children: React.ReactNode }) => {
  const router = useRouter();
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

  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main id="main" className="min-w-0 flex-1">
        <div className="mx-auto max-w-6xl px-6 py-8 md:px-10">{children}</div>
      </main>
    </div>
  );
};

export default DashboardLayout;
