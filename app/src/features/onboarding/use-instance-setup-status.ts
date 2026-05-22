import { hasTurbopufferApiKey } from "@/features/onboarding/onboarding-state";
import { useSession, useSetupStatus } from "@/hooks/use-auth";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { useInstanceSettings } from "@/hooks/use-instance-settings";

export const useInstanceSetupStatus = () => {
  const setupStatus = useSetupStatus();
  const session = useSession();
  const user = session.data?.user ?? null;
  const shouldLoadProviderStatus = Boolean(
    user?.role === "admin" && setupStatus.data?.needs_setup === false,
  );
  const presets = useEmbeddingPresets({ enabled: shouldLoadProviderStatus });
  const settings = useInstanceSettings({ enabled: shouldLoadProviderStatus });
  const presetList = presets.data?.presets ?? [];
  const embeddingComplete = presetList.length > 0;
  const vectorStorageComplete = hasTurbopufferApiKey(settings.data);
  const requiresOnboarding = shouldLoadProviderStatus;
  const complete = requiresOnboarding && embeddingComplete && vectorStorageComplete;
  const providerPending = shouldLoadProviderStatus && (presets.isPending || settings.isPending);
  const providerError = shouldLoadProviderStatus ? (presets.error ?? settings.error) : null;

  return {
    complete,
    embeddingComplete,
    error: setupStatus.error ?? session.error ?? providerError,
    loading: setupStatus.isPending || session.isPending || providerPending,
    needsAdminSetup: Boolean(setupStatus.data?.needs_setup),
    presets: presetList,
    refetch: () => {
      void setupStatus.refetch();
      void session.refetch();
      if (shouldLoadProviderStatus) {
        void presets.refetch();
        void settings.refetch();
      }
    },
    requiresOnboarding,
    session: session.data,
    settings: settings.data,
    vectorStorageComplete,
  };
};
