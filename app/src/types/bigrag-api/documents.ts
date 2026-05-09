export type DocumentStatus = "pending" | "processing" | "ready" | "failed";

export type DocumentProgress = {
  document_id: string;
  collection_name: string;
  step: string;
  status: string;
  message: string;
  progress: number;
  detail: Record<string, unknown>;
};

export type Document = {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: DocumentStatus;
  error_message: string | null;
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  progress: DocumentProgress | null;
};

export type UploadSessionItem = {
  id: string;
  client_item_id: string;
  document_id: string | null;
  filename: string;
  file_type: string;
  file_size: number;
  content_hash: string | null;
  status: "queued" | "ingesting" | "complete" | "failed" | "canceled";
  document_status: DocumentStatus | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type UploadSession = {
  id: string;
  collection_id: string;
  collection_name: string;
  status: "preparing" | "uploading" | "ingesting" | "complete" | "failed" | "canceled";
  total_files: number;
  total_bytes: number;
  uploaded_files: number;
  queued_files: number;
  processing_files: number;
  completed_files: number;
  failed_files: number;
  canceled_files: number;
  active_files: number;
  recent_items: UploadSessionItem[];
  metadata: Record<string, unknown>;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
};

export type UploadSessionFileResponse = {
  item: UploadSessionItem;
  session: UploadSession;
};
