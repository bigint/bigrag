import { createFileRoute } from "@tanstack/react-router";
import { AuthLayout } from "@/layouts/auth-layout";
import { OnboardingPage } from "@/features/onboarding/onboarding-page";

export const Route = createFileRoute("/onboarding")({
  component: () => (
    <AuthLayout>
      <OnboardingPage />
    </AuthLayout>
  ),
});
