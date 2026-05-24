import { useForm, useStore } from "@tanstack/react-form";
import { FolderSync } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Spinner } from "@/components/ui/spinner";
import { Switch } from "@/components/ui/switch";
import { intervalOptions } from "@/features/collections/s3-connector-utils";
import {
  defaultS3SourceFormValues,
  isCloudflareR2Endpoint,
  validateS3SourceFormValues,
} from "@/features/collections/s3-source-form-state";
import { firstString, submitWith } from "@/lib/form";

export const S3SourceForm = ({
  isPending,
  onCancel,
  onSubmit,
  workerOffline,
}: {
  isPending: boolean;
  onCancel: () => void;
  onSubmit: (value: ReturnType<typeof defaultS3SourceFormValues>) => Promise<void> | void;
  workerOffline: boolean;
}) => {
  const form = useForm({
    defaultValues: defaultS3SourceFormValues(),
    validators: {
      onSubmit: ({ value }) => validateS3SourceFormValues(value),
    },
    onSubmit: async ({ value }) => {
      await onSubmit(value);
    },
  });
  const values = useStore(form.store, (state) => state.values);
  const submitError = useStore(form.store, (state) => firstString(state.errors));
  const setEndpointUrl = (endpointUrl: string) => {
    form.setFieldValue("endpointUrl", endpointUrl);
    if (isCloudflareR2Endpoint(endpointUrl)) {
      form.setFieldValue("region", "auto");
    }
  };

  return (
    <form
      className="flex flex-col gap-4"
      noValidate
      onSubmit={submitWith(() => form.handleSubmit())}
    >
      <div className="flex items-center justify-between gap-3 rounded-sm border border-border bg-muted/35 px-3 py-3">
        <div className="min-w-0">
          <div className="truncate text-sm font-semibold">S3 / R2 source</div>
          <div className="mt-0.5 text-xs text-muted-foreground">Bucket prefix mirror</div>
        </div>
        <Badge dot variant={workerOffline ? "warning" : "primary"}>
          {workerOffline ? "worker offline" : "ready"}
        </Badge>
      </div>
      {submitError && (
        <div
          className="rounded-md border border-destructive/30 bg-destructive/10 px-3 py-2 text-sm text-destructive"
          role="alert"
        >
          {submitError}
        </div>
      )}
      <div className="grid gap-4 md:grid-cols-2">
        <Input
          label="Bucket"
          onChange={(event) => form.setFieldValue("bucket", event.target.value)}
          placeholder="company-knowledge"
          value={values.bucket}
        />
        <Input
          label="Prefix"
          onChange={(event) => form.setFieldValue("prefix", event.target.value)}
          placeholder="policies/"
          value={values.prefix}
        />
        <Input
          label="Signing region"
          onChange={(event) => form.setFieldValue("region", event.target.value)}
          placeholder="us-east-1 or auto"
          value={values.region}
        />
        <Input
          label="Endpoint URL"
          onChange={(event) => setEndpointUrl(event.target.value)}
          placeholder="https://account-id.r2.cloudflarestorage.com"
          value={values.endpointUrl}
        />
        <Input
          label="Access key ID"
          onChange={(event) => form.setFieldValue("accessKeyId", event.target.value)}
          value={values.accessKeyId}
        />
        <Input
          label="Secret access key"
          onChange={(event) => form.setFieldValue("secretAccessKey", event.target.value)}
          type="password"
          value={values.secretAccessKey}
        />
        <Input
          label="Session token"
          onChange={(event) => form.setFieldValue("sessionToken", event.target.value)}
          type="password"
          value={values.sessionToken}
        />
        <Select
          label="Sync interval"
          onChange={(value) => form.setFieldValue("syncIntervalHours", value)}
          options={intervalOptions}
          value={values.syncIntervalHours}
        />
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-sm border border-border bg-background p-3">
        <div className="flex flex-wrap items-center gap-5">
          <Switch
            checked={values.scheduleEnabled}
            label="Scheduled"
            onCheckedChange={(checked) => form.setFieldValue("scheduleEnabled", checked)}
          />
          <Switch
            checked={values.forcePathStyle}
            label="Path style"
            onCheckedChange={(checked) => form.setFieldValue("forcePathStyle", checked)}
          />
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button onClick={onCancel} type="button" variant="outline">
            Cancel
          </Button>
          <Button disabled={isPending || workerOffline} type="submit">
            {isPending ? <Spinner /> : <FolderSync className="size-4" />}
            Add source
          </Button>
        </div>
      </div>
    </form>
  );
};
