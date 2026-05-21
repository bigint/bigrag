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
  hasTurbopufferApiKey,
  type TurbopufferDraft,
  turbopufferDraftFromSettings,
  turbopufferSettingsBody,
} from "@/features/onboarding/onboarding-state";
import { PresetSummary, StepPanel } from "@/features/onboarding/onboarding-step-panel";
import { TurbopufferForm } from "@/features/onboarding/turbopuffer-form";
import { useEmbeddingPresets } from "@/hooks/use-embedding-presets";
import { useInstanceSettings, useUpdateInstanceSettings } from "@/hooks/use-instance-settings";

export const OnboardingPage = () => {
  const navigate = useNavigate();
  const presets = useEmbeddingPresets();
  const settings = useInstanceSettings();
  const saveSettings = useUpdateInstanceSettings();
  const [presetOpen, setPresetOpen] = useState(false);
  const [turbopufferSkipped, setTurbopufferSkipped] = useState(false);
  const [draft, setDraft] = useState<TurbopufferDraft>(() =>
    turbopufferDraftFromSettings(undefined),
  );

  useEffect(() => {
    if (settings.data) setDraft(turbopufferDraftFromSettings(settings.data));
  }, [settings.data]);

  const presetList = presets.data?.presets ?? [];
  const firstPreset = presetList[0];
  const embeddingComplete = presetList.length > 0;
  const turbopufferComplete = hasTurbopufferApiKey(settings.data);
  const canSaveTurbopuffer = canSaveTurbopufferDraft(draft, turbopufferComplete);
  const loading = presets.isPending || settings.isPending;
  const error = presets.error ?? settings.error;

  const saveTurbopuffer = async () => {
    if (!canSaveTurbopuffer) {
      toast.error("Add a Turbopuffer API key or skip this step");
      return;
    }
    try {
      await saveSettings.mutateAsync({
        values: turbopufferSettingsBody(draft, turbopufferComplete),
      });
      setTurbopufferSkipped(false);
    } catch {}
  };

  const finish = () => {
    if (!embeddingComplete) return;
    navigate({ to: "/overview", replace: true });
  };

  if (loading) {
    return (
      <div className="flex min-h-[28rem] items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (error) {
    return (
      <Page.Shell>
        <section className="rounded-md border border-destructive/30 bg-destructive/10 p-5">
          <div className="flex items-start gap-3">
            <TriangleAlert className="mt-0.5 size-5 text-destructive" />
            <div className="min-w-0">
              <h1 className="font-semibold text-destructive text-sm">Onboarding unavailable</h1>
              <p className="mt-1 text-destructive/80 text-sm">
                {error instanceof Error ? error.message : "Could not load setup state."}
              </p>
              <Button
                className="mt-4"
                onClick={() => {
                  presets.refetch();
                  settings.refetch();
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

  return (
    <Page.Shell className="max-w-5xl">
      <Page.Header
        actions={
          <Button disabled={!embeddingComplete} onClick={finish} size="lg">
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
            active={!embeddingComplete}
            complete={embeddingComplete}
            icon={Cpu}
            index={1}
            title="Embedding preset"
          >
            {embeddingComplete && firstPreset ? (
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
            active={embeddingComplete && !turbopufferComplete && !turbopufferSkipped}
            complete={turbopufferComplete}
            icon={Database}
            index={2}
            optional
            title="Turbopuffer"
          >
            <TurbopufferForm
              complete={turbopufferComplete}
              draft={draft}
              onDraftChange={setDraft}
              onSave={saveTurbopuffer}
              onSkip={() => {
                setTurbopufferSkipped(true);
                toast.message("Turbopuffer skipped for now");
              }}
              pending={saveSettings.isPending}
              saveDisabled={!canSaveTurbopuffer}
              skipped={turbopufferSkipped}
            />
          </StepPanel>
        </div>

        <ProgressPanel
          embeddingComplete={embeddingComplete}
          onFinish={finish}
          turbopufferComplete={turbopufferComplete}
          turbopufferSkipped={turbopufferSkipped}
        />
      </div>

      <PresetForm editing={null} onClose={() => setPresetOpen(false)} open={presetOpen} />
    </Page.Shell>
  );
};
