import { useCallback, useRef, useState } from "react";
import { toast } from "sonner";
import {
  getWorkerAvailability,
  workerOfflineActionMessage,
} from "@/features/workers/worker-status";
import { useUploadSessionDocuments } from "@/hooks/use-documents";
import { usePlatformStats } from "@/hooks/use-platform";
import { filterBlockedFiles } from "@/lib/file-types";
import { formatBytes } from "@/lib/format";

const fileDisplayName = (file: File) =>
  (file as File & { webkitRelativePath?: string }).webkitRelativePath || file.name;

const countDuplicateNames = (files: File[]) => {
  const seen = new Set<string>();
  let count = 0;
  for (const file of files) {
    const name = fileDisplayName(file);
    if (seen.has(name)) count += 1;
    seen.add(name);
  }
  return count;
};

interface UseDocumentUploadOptions {
  readonly name: string;
  readonly allowed: string[];
  readonly setActiveSessionId: (name: string, sessionId: string) => void;
}

export const useDocumentUpload = ({
  name,
  allowed,
  setActiveSessionId,
}: UseDocumentUploadOptions) => {
  const { data: stats } = usePlatformStats();
  const upload = useUploadSessionDocuments(name, {
    onSessionStart: (session) => setActiveSessionId(name, session.id),
  });
  const [dragging, setDragging] = useState(false);
  const fileInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const workerAvailability = getWorkerAvailability(stats);
  const workerOffline = workerAvailability.offline;

  const onFiles = useCallback(
    async (files: FileList | File[]) => {
      if (workerOffline) {
        toast.warning(workerOfflineActionMessage(workerAvailability));
        return;
      }
      const arr = Array.from(files);
      if (!arr.length) return;
      const { accepted, rejected } = filterBlockedFiles(arr, allowed);
      if (rejected.length) {
        toast.warning(
          `${rejected.length} file${rejected.length === 1 ? "" : "s"} skipped — not allowed in this collection.`,
        );
      }
      if (accepted.length) {
        const duplicateCount = countDuplicateNames(accepted);
        if (duplicateCount) {
          toast.info(
            `${duplicateCount} duplicate filename${duplicateCount === 1 ? "" : "s"} selected`,
          );
        }
        const totalSize = accepted.reduce((sum, file) => sum + file.size, 0);
        toast.info(
          `${accepted.length} file${accepted.length === 1 ? "" : "s"} selected (${formatBytes(totalSize)})`,
        );
        const res = await upload.mutateAsync(accepted);
        setActiveSessionId(name, res.session.id);
        if (fileInput.current) fileInput.current.value = "";
        if (folderInput.current) folderInput.current.value = "";
      }
    },
    [upload, allowed, name, setActiveSessionId, workerAvailability, workerOffline],
  );

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragging(false);
    if (e.dataTransfer.files.length) onFiles(e.dataTransfer.files);
  };

  return {
    upload,
    dragging,
    setDragging,
    fileInput,
    folderInput,
    workerAvailability,
    workerOffline,
    onFiles,
    onDrop,
  };
};
