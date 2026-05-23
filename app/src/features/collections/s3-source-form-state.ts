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

export const isCloudflareR2Endpoint = (endpointUrl: string): boolean => {
  const value = endpointUrl.trim();
  if (!value) return false;
  try {
    const parsed = new URL(value.includes("://") ? value : `https://${value}`);
    const host = parsed.hostname.toLowerCase().replace(/\.$/, "");
    return host === "r2.cloudflarestorage.com" || host.endsWith(".r2.cloudflarestorage.com");
  } catch {
    return value.toLowerCase().includes("r2.cloudflarestorage.com");
  }
};

export const normalizedS3SourceRegion = (region: string, endpointUrl: string) =>
  isCloudflareR2Endpoint(endpointUrl) ? "auto" : region.trim() || "us-east-1";

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
  secretAccessKey,
}: S3SourceFormValues): string | undefined => {
  if (!bucket.trim()) return "Bucket is required";
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
  region: normalizedS3SourceRegion(region, endpointUrl),
  schedule_enabled: scheduleEnabled,
  secret_access_key: secretAccessKey.trim(),
  session_token: sessionToken.trim() || null,
  sync_interval_hours: Number(syncIntervalHours),
});
