import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import {
  type CreateCollectionForm,
  DEFAULT_METADATA_SCHEMA,
} from "@/features/collections/create-collection/create-collection-form";
import { ToggleFieldCard } from "@/features/collections/create-collection/toggle-field-card";
import { errorText } from "@/lib/form";

export const AdvancedSafeguards = ({
  form,
  values,
  onToggleMultimodal,
  onToggleMultimodalEnrichment,
  onToggleTenantGuard,
  onToggleMetadataSchema,
}: {
  form: CreateCollectionForm;
  values: {
    multimodalEnabled: boolean;
    multimodalEnrichmentEnabled: boolean;
    tenantGuardEnabled: boolean;
    metadataSchemaEnabled: boolean;
  };
  onToggleMultimodal: (enabled: boolean) => void;
  onToggleMultimodalEnrichment: (enabled: boolean) => void;
  onToggleTenantGuard: (enabled: boolean) => void;
  onToggleMetadataSchema: (enabled: boolean) => void;
}) => (
  <details className="rounded-md border border-border bg-muted/30">
    <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-3 py-3 [&::-webkit-details-marker]:hidden">
      <div>
        <div className="text-sm font-semibold">Advanced safeguards</div>
        <p className="mt-0.5 text-xs text-muted-foreground">
          Optional rules for multi-customer data and uploaded metadata.
        </p>
      </div>
      <span className="text-xs font-medium text-muted-foreground">Configure</span>
    </summary>
    <div className="space-y-3 border-t border-border px-3 py-3">
      <ToggleFieldCard
        ariaLabel="Store document elements"
        checked={values.multimodalEnabled}
        description="Preserve headings, tables, equations, images, page bounds, and asset refs."
        onCheckedChange={onToggleMultimodal}
        title="Store document elements"
      >
        <div className="mt-3 flex items-start justify-between gap-3 rounded-md border border-border bg-muted/30 p-3">
          <div>
            <div className="text-sm font-semibold">LLM enrichment</div>
            <p className="mt-1 text-xs text-muted-foreground">
              Queue generated summaries for tables, equations, and images.
            </p>
          </div>
          <Switch
            aria-label="LLM enrichment"
            checked={values.multimodalEnrichmentEnabled}
            onCheckedChange={onToggleMultimodalEnrichment}
          />
        </div>
      </ToggleFieldCard>
      <ToggleFieldCard
        ariaLabel="Separate customer data"
        checked={values.tenantGuardEnabled}
        description="Require every upload and search to include one customer key."
        onCheckedChange={onToggleTenantGuard}
        title="Separate customer data"
      >
        <form.Field
          name="tenantField"
          validators={{
            onSubmit: ({ value }) => {
              if (!value.trim()) return "Enter the tenant metadata key";
              return value.trim().length > 64
                ? "Tenant field must be 64 characters or fewer"
                : undefined;
            },
          }}
        >
          {(field) => (
            <div className="mt-3">
              <Input
                description="Uploads and searches must include this metadata key."
                error={errorText(field.state.meta.errors)}
                label="Customer metadata key"
                maxLength={64}
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder="tenant_id"
                value={field.state.value}
              />
            </div>
          )}
        </form.Field>
      </ToggleFieldCard>
      <ToggleFieldCard
        ariaLabel="Validate uploaded metadata"
        checked={values.metadataSchemaEnabled}
        description="Reject uploads whose metadata does not match a JSON schema."
        onCheckedChange={onToggleMetadataSchema}
        title="Validate uploaded metadata"
      >
        <form.Field name="metadataSchemaText">
          {(field) => (
            <div className="mt-3">
              <Textarea
                className="min-h-28 font-mono"
                label="JSON schema"
                onBlur={field.handleBlur}
                onChange={(e) => field.handleChange(e.target.value)}
                placeholder={DEFAULT_METADATA_SCHEMA}
                value={field.state.value}
              />
            </div>
          )}
        </form.Field>
      </ToggleFieldCard>
    </div>
  </details>
);
