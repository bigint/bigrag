"use client";

import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";

const Home = () => {
  const router = useRouter();
  const { data: setupStatus, isPending: setupPending } = useSetupStatus();
  const { data: session, isPending: sessionPending, isError } = useSession();

  useEffect(() => {
    if (setupPending || sessionPending) return;
    if (setupStatus?.needs_setup) {
      router.replace("/setup");
    } else if (session && !isError) {
      router.replace("/overview");
    } else {
      router.replace("/login");
    }
  }, [setupStatus, session, setupPending, sessionPending, isError, router]);

  return (
    <div className="flex min-h-svh items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
};

export default Home;
