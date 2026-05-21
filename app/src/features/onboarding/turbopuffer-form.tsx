import { ArrowRight, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import type { TurbopufferDraft } from "@/features/onboarding/onboarding-state";

type TurbopufferFormProps = {
  readonly complete: boolean;
  readonly draft: TurbopufferDraft;
  readonly onDraftChange: (draft: TurbopufferDraft) => void;
  readonly onSave: () => void;
  readonly onSkip: () => void;
  readonly pending: boolean;
  readonly saveDisabled: boolean;
  readonly skipped: boolean;
};

export const TurbopufferForm = ({
  complete,
  draft,
  onDraftChange,
  onSave,
  onSkip,
  pending,
  saveDisabled,
  skipped,
}: TurbopufferFormProps) => {
  const patchDraft = (patch: Partial<TurbopufferDraft>) => onDraftChange({ ...draft, ...patch });
  return (
    <form
      className="flex flex-col gap-4"
      onSubmit={(event) => {
        event.preventDefault();
        onSave();
      }}
    >
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          description={complete ? "Leave blank to keep the saved key." : undefined}
          label="API key"
          onChange={(event) => patchDraft({ apiKey: event.target.value })}
          placeholder={complete ? "Saved" : "tpuf_..."}
          type="password"
          value={draft.apiKey}
        />
        <Input
          label="Region"
          onChange={(event) => patchDraft({ region: event.target.value })}
          placeholder="aws-us-east-1"
          value={draft.region}
        />
        <Input
          label="Namespace prefix"
          onChange={(event) => patchDraft({ namespacePrefix: event.target.value })}
          placeholder="bigrag_"
          value={draft.namespacePrefix}
        />
        <Input
          label="Base URL"
          onChange={(event) => patchDraft({ baseUrl: event.target.value })}
          placeholder="https://api.turbopuffer.com"
          value={draft.baseUrl}
        />
      </div>
      <div className="flex flex-col gap-3 border-border border-t pt-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 text-muted-foreground text-sm">
          {complete
            ? "Turbopuffer is configured for this instance."
            : skipped
              ? "Skipped for now. System health will keep reporting vector readiness."
              : "Save a working vector store now, or skip and configure it later."}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          {!complete && (
            <Button disabled={pending} onClick={onSkip} type="button" variant="secondary">
              Skip for now
              <ArrowRight className="size-4" />
            </Button>
          )}
          <Button disabled={pending || saveDisabled} type="submit">
            {pending ? (
              <Spinner className="border-primary-foreground" size="sm" />
            ) : (
              <Save className="size-4" />
            )}
            {complete ? "Update Turbopuffer" : "Save Turbopuffer"}
          </Button>
        </div>
      </div>
    </form>
  );
};
