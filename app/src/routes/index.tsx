import { useQueryClient } from "@tanstack/react-query";
import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { ApiUnreachable } from "@/components/status/api-unreachable";
import { Spinner } from "@/components/ui/spinner";
import { useInstanceSetupStatus } from "@/features/onboarding/use-instance-setup-status";
import { queryKeys } from "@/lib/query-keys";

export const Route = createFileRoute("/")({
  component: () => <Home />,
});

const Home = () => {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const setup = useInstanceSetupStatus();

  useHomeRedirect(setup, navigate);

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

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
};

type HomeRedirectState = ReturnType<typeof useInstanceSetupStatus>;

const useHomeRedirect = (setup: HomeRedirectState, navigate: ReturnType<typeof useNavigate>) => {
  useEffect(() => {
    if (setup.loading || setup.error) return;
    if (setup.needsAdminSetup) {
      navigate({ to: "/setup", replace: true });
    } else if (!setup.session) {
      navigate({ to: "/login", replace: true });
    } else if (setup.requiresOnboarding && !setup.complete) {
      navigate({ to: "/onboarding", replace: true });
    } else {
      navigate({ to: "/overview", replace: true });
    }
  }, [
    navigate,
    setup.complete,
    setup.error,
    setup.loading,
    setup.needsAdminSetup,
    setup.requiresOnboarding,
    setup.session,
  ]);
};
