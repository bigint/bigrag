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

  useEffect(() => {
    if (setupPending || sessionPending) return;
    if (setupStatus?.needs_setup) {
      navigate({ to: "/setup", replace: true });
    } else if (session && !isError) {
      navigate({ to: "/overview", replace: true });
    } else {
      navigate({ to: "/login", replace: true });
    }
  }, [setupStatus, session, setupPending, sessionPending, isError, navigate]);

  return (
    <div className="flex min-h-screen items-center justify-center">
      <Spinner size="lg" />
    </div>
  );
};
