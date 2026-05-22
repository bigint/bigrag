import { createFileRoute } from "@tanstack/react-router";
import { OnboardingPage } from "@/features/onboarding/onboarding-page";
import { AuthLayout } from "@/layouts/auth-layout";

export const Route = createFileRoute("/onboarding")({
  component: () => (
    <AuthLayout>
      <OnboardingPage />
    </AuthLayout>
  ),
});
