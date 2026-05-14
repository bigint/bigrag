import { useEffect, useMemo } from "react";
import type { GoogleDriveFileList, GoogleDriveSyncJob } from "@/types/bigrag";

export const useSyncJobsBySource = (jobs: GoogleDriveSyncJob[] | undefined) =>
  useMemo(() => {
    const map = new Map<string, GoogleDriveSyncJob>();
    for (const job of jobs ?? []) {
      if (!job.source_id) continue;
      if (!map.has(job.source_id)) map.set(job.source_id, job);
    }
    return map;
  }, [jobs]);

export const useVisibleGoogleDriveFiles = (
  collection: string,
  fileList: GoogleDriveFileList | undefined,
  pageToken: string | undefined,
  syncVisibleFiles: (
    collection: string,
    fileList: GoogleDriveFileList | undefined,
    pageToken: string | undefined,
  ) => void,
) => {
  useEffect(() => {
    syncVisibleFiles(collection, fileList, pageToken);
  }, [collection, fileList, pageToken, syncVisibleFiles]);
};
