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

export type FileInput = File | Blob | Buffer | Uint8Array | { path: string; name?: string };
