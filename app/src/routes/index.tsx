import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { useSession, useSetupStatus } from "@/hooks/use-auth";

export const Route = createFileRoute("/")({
  component: () => <Home />,
});

const Home = () => {
  const navigate = useNavigate();
  const { data: setupStatus, isPending: setupPending } = useSetupStatus();
  const { data: session, isPending: sessionPending, isError } = useSession();

  useHomeRedirect(
    {
      hasSession: Boolean(session),
      isError,
      sessionPending,
      setupNeedsSetup: setupStatus?.needs_setup,
      setupPending,
    },
    navigate,
  );

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
  readonly setupNeedsSetup: boolean | undefined;
  readonly setupPending: boolean;
};

const useHomeRedirect = (
  { hasSession, isError, sessionPending, setupNeedsSetup, setupPending }: HomeRedirectState,
  navigate: ReturnType<typeof useNavigate>,
) => {
  useEffect(() => {
    if (setupPending || sessionPending) return;
    if (setupNeedsSetup) {
      navigate({ to: "/setup", replace: true });
    } else if (hasSession && !isError) {
      navigate({ to: "/overview", replace: true });
    } else {
      navigate({ to: "/login", replace: true });
    }
  }, [hasSession, isError, sessionPending, setupNeedsSetup, setupPending, navigate]);
};
