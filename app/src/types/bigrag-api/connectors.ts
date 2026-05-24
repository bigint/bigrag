import type { S3SourceListResponse, S3SyncJobListResponse } from "@bigrag/client/browser";

export type {
  ConnectorSyncJobDetails,
  ConnectorSyncProgress,
  ConnectorSyncProgressPhase,
  CreateS3SourceBody,
  S3Source,
  S3SyncJob,
  UpdateS3SourceBody,
} from "@bigrag/client/browser";

export type S3SourceList = S3SourceListResponse;
export type S3SyncJobList = S3SyncJobListResponse;
