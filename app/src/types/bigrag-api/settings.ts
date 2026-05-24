import type { InstanceSetting, BackupJob as SdkBackupJob } from "@bigrag/client";
import type { Paginated } from "@/types/pagination";

export type {
  InstanceSettingGroup,
  InstanceSettingKind,
  InstanceSettingSpec,
  InstanceSettingsResponse,
} from "@bigrag/client";

export type InstanceSettingValue = InstanceSetting;

export type BackupJob = Omit<SdkBackupJob, "status"> & {
  status: "pending" | "running" | "succeeded" | "failed";
};

export type BackupJobListResponse = Paginated<"jobs", BackupJob>;
