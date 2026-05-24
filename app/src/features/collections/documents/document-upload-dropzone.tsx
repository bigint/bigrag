import { FolderOpen, Upload } from "lucide-react";
import type { DragEventHandler, RefObject } from "react";
import { Button } from "@/components/ui/button";
import type { WorkerAvailability } from "@/features/workers/worker-status";
import { workerOfflineActionMessage } from "@/features/workers/worker-status";
import { cn } from "@/lib/cn";

interface DocumentUploadDropzoneProps {
  readonly accept: string;
  readonly acceptedDescription: string;
  readonly dragging: boolean;
  readonly fileInput: RefObject<HTMLInputElement | null>;
  readonly folderInput: RefObject<HTMLInputElement | null>;
  readonly onDrop: DragEventHandler<HTMLFieldSetElement>;
  readonly onFiles: (files: FileList) => void;
  readonly setDragging: (dragging: boolean) => void;
  readonly uploadPending: boolean;
  readonly workerAvailability: WorkerAvailability;
  readonly workerOffline: boolean;
}

export const DocumentUploadDropzone = ({
  accept,
  acceptedDescription,
  dragging,
  fileInput,
  folderInput,
  onDrop,
  onFiles,
  setDragging,
  uploadPending,
  workerAvailability,
  workerOffline,
}: DocumentUploadDropzoneProps) => (
  <fieldset
    aria-label="Document upload"
    className={cn(
      "flex flex-col items-center justify-center gap-4 rounded-xl border border-dashed px-6 py-8 text-sm",
      "border-border bg-card hover:border-primary hover:bg-accent/50",
      dragging && !workerOffline && "border-primary bg-accent",
      uploadPending && "pointer-events-none opacity-60",
      workerOffline && "bg-muted/45 hover:border-border hover:bg-muted/45",
    )}
    onDragLeave={() => setDragging(false)}
    onDragOver={(event) => {
      event.preventDefault();
      setDragging(true);
    }}
    onDrop={onDrop}
  >
    <div className="flex items-center gap-3">
      <Upload className="size-5 text-muted-foreground" />
      <div className="flex flex-col items-start gap-0.5">
        <span className="font-medium">
          {uploadPending ? "Uploading…" : workerOffline ? "Worker offline" : "Drop files here"}
        </span>
        <span className="text-xs text-muted-foreground">{acceptedDescription}</span>
      </div>
    </div>
    <div className="flex flex-wrap items-center justify-center gap-2">
      <Button
        disabled={uploadPending || workerOffline}
        onClick={() => fileInput.current?.click()}
        size="sm"
        title={workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined}
      >
        <Upload className="size-4" />
        Files
      </Button>
      <Button
        disabled={uploadPending || workerOffline}
        onClick={() => folderInput.current?.click()}
        size="sm"
        title={workerOffline ? workerOfflineActionMessage(workerAvailability) : undefined}
        variant="secondary"
      >
        <FolderOpen className="size-4" />
        Folder
      </Button>
    </div>
    <input
      accept={accept}
      className="sr-only"
      disabled={workerOffline}
      id="doc-upload"
      multiple
      onChange={(event) => event.target.files && onFiles(event.target.files)}
      ref={fileInput}
      type="file"
    />
    <input
      accept={accept}
      className="sr-only"
      disabled={workerOffline}
      multiple
      onChange={(event) => event.target.files && onFiles(event.target.files)}
      ref={folderInput}
      type="file"
      {...{ webkitdirectory: "", directory: "" }}
    />
  </fieldset>
);
