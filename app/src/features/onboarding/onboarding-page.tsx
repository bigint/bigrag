import { useNavigate } from "@tanstack/react-router";
import { CheckCircle2, Cpu, Database, Plus, TriangleAlert } from "lucide-react";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Page } from "@/components/ui/page";
import { Spinner } from "@/components/ui/spinner";
import { PresetForm } from "@/features/models/preset-form";
import { ProgressPanel } from "@/features/onboarding/onboarding-progress";
import {
  canSaveTurbopufferDraft,
  type TurbopufferDraft,
  turbopufferDraftFromSettings,
  turbopufferSettingsBody,
} from "@/features/onboarding/onboarding-state";
import { PresetSummary, StepPanel } from "@/features/onboarding/onboarding-step-panel";
import { TurbopufferForm } from "@/features/onboarding/turbopuffer-form";
import { useInstanceSetupStatus } from "@/features/onboarding/use-instance-setup-status";
import { useUpdateInstanceSettings } from "@/hooks/use-instance-settings";

export const OnboardingPage = () => {
  const navigate = useNavigate();
  const setup = useInstanceSetupStatus();
  const saveSettings = useUpdateInstanceSettings();
  const [presetOpen, setPresetOpen] = useState(false);
  const [draft, setDraft] = useState<TurbopufferDraft>(() =>
    turbopufferDraftFromSettings(undefined),
  );

  useEffect(() => {
    if (setup.settings) setDraft(turbopufferDraftFromSettings(setup.settings));
  }, [setup.settings]);

  useEffect(() => {
    if (setup.loading || setup.error) return;
    if (setup.needsAdminSetup) {
      navigate({ to: "/setup", replace: true });
      return;
    }
    if (!setup.session) {
      navigate({ to: "/login", search: { from: "/onboarding" }, replace: true });
      return;
    }
    if (!setup.requiresOnboarding) {
      navigate({ to: "/overview", replace: true });
    }
  }, [
    navigate,
    setup.error,
    setup.loading,
    setup.needsAdminSetup,
    setup.requiresOnboarding,
    setup.session,
  ]);

  const presetList = setup.presets;
  const firstPreset = presetList[0];
  const canSaveTurbopuffer = canSaveTurbopufferDraft(draft, setup.vectorStorageComplete);

  const saveTurbopuffer = async () => {
    if (!canSaveTurbopuffer) {
      toast.error("Add a Turbopuffer API key");
      return;
    }
    try {
      await saveSettings.mutateAsync({
        values: turbopufferSettingsBody(draft, setup.vectorStorageComplete),
      });
    } catch {}
  };

  const finish = () => {
    if (!setup.complete) return;
    navigate({ to: "/overview", replace: true });
  };

  if (setup.error) {
    return (
      <Page.Shell>
        <section className="rounded-md border border-destructive/30 bg-destructive/10 p-5">
          <div className="flex items-start gap-3">
            <TriangleAlert className="mt-0.5 size-5 text-destructive" />
            <div className="min-w-0">
              <h1 className="font-semibold text-destructive text-sm">Onboarding unavailable</h1>
              <p className="mt-1 text-destructive/80 text-sm">
                {setup.error instanceof Error ? setup.error.message : "Could not load setup state."}
              </p>
              <Button
                className="mt-4"
                onClick={() => {
                  setup.refetch();
                }}
                variant="secondary"
              >
                Retry
              </Button>
            </div>
          </div>
        </section>
      </Page.Shell>
    );
  }

  if (setup.loading || setup.needsAdminSetup || !setup.session || !setup.requiresOnboarding) {
    return (
      <div className="flex min-h-[28rem] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  return (
    <Page.Shell className="max-w-5xl">
      <Page.Header
        actions={
          <Button disabled={!setup.complete} onClick={finish} size="lg">
            <CheckCircle2 className="size-4" />
            Finish setup
          </Button>
        }
        description="Connect the provider pieces bigRAG needs before indexing documents."
        eyebrow={<Badge variant="primary">First-run onboarding</Badge>}
        title="Connect providers"
      />

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_18rem]">
        <div className="flex min-w-0 flex-col gap-4">
          <StepPanel
            active={!setup.embeddingComplete}
            complete={setup.embeddingComplete}
            icon={Cpu}
            index={1}
            title="Embedding preset"
          >
            {setup.embeddingComplete && firstPreset ? (
              <PresetSummary preset={firstPreset} total={presetList.length} />
            ) : (
              <div className="flex flex-col gap-4">
                <p className="text-muted-foreground text-sm leading-6">
                  Create one verified embedding preset. Collections can reuse it when they are
                  created.
                </p>
                <div>
                  <Button onClick={() => setPresetOpen(true)}>
                    <Plus className="size-4" />
                    Create embedding preset
                  </Button>
                </div>
              </div>
            )}
          </StepPanel>

          <StepPanel
            active={setup.embeddingComplete && !setup.vectorStorageComplete}
            complete={setup.vectorStorageComplete}
            icon={Database}
            index={2}
            title="Vector storage"
          >
            <TurbopufferForm
              complete={setup.vectorStorageComplete}
              draft={draft}
              onDraftChange={setDraft}
              onSave={saveTurbopuffer}
              pending={saveSettings.isPending}
              saveDisabled={!canSaveTurbopuffer}
            />
          </StepPanel>
        </div>

        <ProgressPanel
          embeddingComplete={setup.embeddingComplete}
          onFinish={finish}
          setupComplete={setup.complete}
          vectorStorageComplete={setup.vectorStorageComplete}
        />
      </div>

      <PresetForm editing={null} onClose={() => setPresetOpen(false)} open={presetOpen} />
    </Page.Shell>
  );
};
