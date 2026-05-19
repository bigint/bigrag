import { useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { useSession, useSetupStatus } from "@/hooks/use-auth";

type Gate = "auth" | "setup-needed" | "logged-in" | "logged-out";

type Options = {
  readonly when: Gate;
  readonly to: string;
  readonly search?: Record<string, unknown>;
};

export const useAuthGate = ({ when, to, search }: Options) => {
  const navigate = useNavigate();
  const { data: setupStatus, isError: setupIsError, isPending: setupPending } = useSetupStatus();
  const { data: session, isError: sessionIsError, isPending: sessionPending } = useSession();

  useEffect(() => {
    if (setupPending || sessionPending) return;
    if (when === "setup-needed") {
      if (!setupIsError && setupStatus?.needs_setup) {
        navigate({ to, replace: true, ...(search ? { search } : {}) });
      }
      return;
    }
    if (when === "auth") {
      if (!sessionIsError && setupStatus && !setupStatus.needs_setup) {
        navigate({ to, replace: true, ...(search ? { search } : {}) });
      }
      return;
    }
    if (when === "logged-in") {
      if (setupIsError || sessionIsError) return;
      if (setupStatus?.needs_setup) return;
      if (session) {
        navigate({ to, replace: true, ...(search ? { search } : {}) });
      }
      return;
    }
    if (when === "logged-out") {
      if (setupIsError || sessionIsError) return;
      if (setupStatus?.needs_setup) return;
      if (!session) {
        navigate({ to, replace: true, ...(search ? { search } : {}) });
      }
    }
  }, [
    navigate,
    search,
    session,
    sessionIsError,
    sessionPending,
    setupIsError,
    setupPending,
    setupStatus,
    to,
    when,
  ]);
};
