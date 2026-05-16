import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/")({
  component: () => <Home />,
});

const Home = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const {
    data: setupStatus,
    error: setupError,
    isError: setupIsError,
    isPending: setupPending,
  } = useSetupStatus();
  const { data: session, error: sessionError, isError, isPending: sessionPending } = useSession();

  useHomeRedirect(
    {
      hasSession: Boolean(session),
      isError,
      sessionPending,
      setupIsError,
      setupNeedsSetup: setupStatus?.needs_setup,
      setupPending,
    },
    navigate,
  );

  const error = setupError ?? sessionError;
  if (error) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-background px-6">
        <div className="w-full max-w-md rounded-xl border border-border bg-card p-6">
          <h1 className="text-base font-semibold">API unreachable</h1>
          <p className="mt-2 text-sm text-muted-foreground">
            {error instanceof Error ? error.message : "The bigRAG API did not respond."}
          </p>
          <Button
            className="mt-4"
            onClick={() => queryClient.invalidateQueries({ queryKey: queryKeys.auth.all() })}
          >
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
};

type HomeRedirectState = {
  readonly hasSession: boolean;
  readonly isError: boolean;
  readonly sessionPending: boolean;
  readonly setupIsError: boolean;
  readonly setupNeedsSetup: boolean | undefined;
  readonly setupPending: boolean;
};

const useHomeRedirect = (
  {
    hasSession,
    isError,
    sessionPending,
    setupIsError,
    setupNeedsSetup,
    setupPending,
  }: HomeRedirectState,
  navigate: ReturnType<typeof useNavigate>,
) => {
  useEffect(() => {
    if (setupPending || sessionPending || setupIsError || isError) return;
    if (setupNeedsSetup) {
      navigate({ to: "/setup", replace: true });
    } else if (hasSession) {
      navigate({ to: "/overview", replace: true });
    } else {
      navigate({ to: "/login", replace: true });
    }
  }, [hasSession, isError, sessionPending, setupIsError, setupNeedsSetup, setupPending, navigate]);
};
