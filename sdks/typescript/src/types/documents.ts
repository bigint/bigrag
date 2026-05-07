export interface DocumentProgress {
  document_id: string;
  collection_name: string;
  step: string;
  status: string;
  message: string;
  progress: number;
  detail: Record<string, unknown>;
}

export interface Document {
  id: string;
  collection_id: string;
  filename: string;
  file_type: string;
  file_size: number;
  chunk_count: number;
  status: string;
  error_message: string | null;
  metadata: Record<string, unknown>;
  content_hash: string | null;
  deduped: boolean;
  progress: DocumentProgress | null;
  created_at: string;
  updated_at: string;
}

export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

export interface DocumentListOptions {
  status?: string;
  limit?: number;
  offset?: number;
}

export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
}

export interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
  total: number;
}

export interface BatchStatusBody {
  document_ids: string[];
}

export interface DocumentStatus {
  id: string;
  status: string;
  error_message: string | null;
  chunk_count: number;
  progress: DocumentProgress | null;
}

export interface BatchStatusResponse {
  documents: DocumentStatus[];
  total: number;
}

export interface BatchGetDocumentsResponse {
  documents: Document[];
  total: number;
}

export interface BatchDeleteBody {
  document_ids: string[];
}

export interface BatchDeleteDocumentsResponse {
  status: string;
  deleted: number;
  errors: Array<{ document_id: string; error: string }>;
}

export interface UploadSessionCreateRequest {
  total_files: number;
  total_bytes: number;
  metadata?: Record<string, unknown>;
}

export interface UploadSessionItem {
  id: string;
  client_item_id: string;
  document_id: string | null;
  filename: string;
  file_type: string;
  file_size: number;
  content_hash: string | null;
  status: string;
  document_status: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface UploadSession {
  id: string;
  collection_id: string;
  collection_name: string;
  status: string;
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
}

export interface UploadSessionFileResponse {
  item: UploadSessionItem;
  session: UploadSession;
}

export type FileInput = File | Blob | Buffer | Uint8Array | { path: string; name?: string };
