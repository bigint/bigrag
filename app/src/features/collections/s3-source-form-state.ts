export type S3SourceFormValues = {
  accessKeyId: string;
  bucket: string;
  endpointUrl: string;
  forcePathStyle: boolean;
  prefix: string;
  region: string;
  scheduleEnabled: boolean;
  secretAccessKey: string;
  sessionToken: string;
  syncIntervalHours: string;
};

export const defaultS3SourceFormValues = (): S3SourceFormValues => ({
  accessKeyId: "",
  bucket: "",
  endpointUrl: "",
  forcePathStyle: false,
  prefix: "",
  region: "us-east-1",
  scheduleEnabled: true,
  secretAccessKey: "",
  sessionToken: "",
  syncIntervalHours: "24",
});

export const validateS3SourceFormValues = ({
  accessKeyId,
  bucket,
  region,
  secretAccessKey,
}: S3SourceFormValues): string | undefined => {
  if (!bucket.trim()) return "Bucket is required";
  if (!region.trim()) return "Region is required";
  if (!accessKeyId.trim()) return "Access key ID is required";
  if (!secretAccessKey.trim()) return "Secret access key is required";
  return undefined;
};

export const s3SourcePayload = ({
  accessKeyId,
  bucket,
  endpointUrl,
  forcePathStyle,
  prefix,
  region,
  scheduleEnabled,
  secretAccessKey,
  sessionToken,
  syncIntervalHours,
}: S3SourceFormValues) => ({
  access_key_id: accessKeyId.trim(),
  bucket: bucket.trim(),
  endpoint_url: endpointUrl.trim() || null,
  force_path_style: forcePathStyle,
  prefix: prefix.trim(),
  region: region.trim(),
  schedule_enabled: scheduleEnabled,
  secret_access_key: secretAccessKey.trim(),
  session_token: sessionToken.trim() || null,
  sync_interval_hours: Number(syncIntervalHours),
});
