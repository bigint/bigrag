import type {
  Document as SdkDocument,
  DocumentProgress as SdkDocumentProgress,
  UploadSession as SdkUploadSession,
  UploadSessionFileResponse as SdkUploadSessionFileResponse,
  UploadSessionItem as SdkUploadSessionItem,
} from "@bigrag/client";

export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export type DocumentProgress = SdkDocumentProgress;

export type Document = Omit<SdkDocument, "status" | "progress"> & {
  status: DocumentStatus;
  progress: DocumentProgress | null;
};

type UploadSessionItem = Omit<SdkUploadSessionItem, "status" | "document_status"> & {
  status: "queued" | "ingesting" | "complete" | "failed" | "canceled";
  document_status: DocumentStatus | null;
};

export type UploadSession = Omit<SdkUploadSession, "status" | "recent_items"> & {
  status: "preparing" | "uploading" | "ingesting" | "complete" | "failed" | "canceled";
  recent_items: UploadSessionItem[];
};

export type UploadSessionFileResponse = Omit<SdkUploadSessionFileResponse, "item" | "session"> & {
  item: UploadSessionItem;
  session: UploadSession;
};

export type DocumentListSort =
  | "created_at"
  | "updated_at"
  | "filename"
  | "file_size"
  | "chunk_count"
  | "status";

export type DocumentListOrder = "asc" | "desc";

export type DocumentListFilters = {
  q?: string;
  status?: string;
  sort?: DocumentListSort;
  order?: DocumentListOrder;
  limit?: number;
  offset?: number;
};
