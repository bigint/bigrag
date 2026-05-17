import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { ApiUnreachable } from "@/components/status/api-unreachable";
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
      <ApiUnreachable
        error={error}
        onRetry={() => queryClient.invalidateQueries({ queryKey: queryKeys.auth.all() })}
      />
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
