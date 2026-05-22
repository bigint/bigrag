import { Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import type { TurbopufferDraft } from "@/features/onboarding/onboarding-state";
import { TURBOPUFFER_REGION_OPTIONS } from "@/features/turbopuffer/region-options";

type TurbopufferFormProps = {
  readonly complete: boolean;
  readonly draft: TurbopufferDraft;
  readonly onDraftChange: (draft: TurbopufferDraft) => void;
  readonly onSave: () => void;
  readonly pending: boolean;
  readonly saveDisabled: boolean;
  readonly saveLabel: string;
};

export const TurbopufferForm = ({
  complete,
  draft,
  onDraftChange,
  onSave,
  pending,
  saveDisabled,
  saveLabel,
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
        <Select
          label="Region"
          onChange={(value) => patchDraft({ region: value })}
          options={TURBOPUFFER_REGION_OPTIONS}
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
            ? "Vector storage is configured for this instance."
            : "Save a working Turbopuffer connection before entering the dashboard."}
        </div>
        <div className="flex shrink-0 flex-wrap gap-2">
          <Button disabled={pending || saveDisabled} type="submit">
            {pending ? (
              <Spinner className="border-primary-foreground" size="sm" />
            ) : (
              <Save className="size-4" />
            )}
            {complete ? "Update vector storage" : saveLabel}
          </Button>
        </div>
      </div>
    </form>
  );
};
