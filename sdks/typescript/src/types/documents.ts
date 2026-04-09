/** A document stored within a collection. */
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
  created_at: string;
  updated_at: string;
}

/** Paginated list of documents. */
export interface DocumentListResponse {
  documents: Document[];
  total: number;
}

/** Options for listing documents. */
export interface DocumentListOptions {
  status?: string;
  limit?: number;
  offset?: number;
}

/** A single chunk extracted from a document. */
export interface DocumentChunk {
  id: string;
  document_id: string;
  chunk_index: number;
  text: string;
  metadata: Record<string, unknown>;
}

/** Paginated list of document chunks. */
export interface DocumentChunkListResponse {
  chunks: DocumentChunk[];
  total: number;
}

/** Body for batch status requests. */
export interface BatchStatusBody {
  document_ids: string[];
}

/** Status of a single document in a batch response. */
export interface DocumentStatus {
  id: string;
  status: string;
  error_message: string | null;
  chunk_count: number;
}

/** Response for batch document status check. */
export interface BatchStatusResponse {
  documents: DocumentStatus[];
  total: number;
}

/** Response for batch document retrieval. */
export interface BatchGetDocumentsResponse {
  documents: Document[];
  total: number;
}

/** Body for batch document deletion. */
export interface BatchDeleteBody {
  document_ids: string[];
}

/** Response for batch document deletion. */
export interface BatchDeleteDocumentsResponse {
  status: string;
  deleted: number;
  errors: Array<{ document_id: string; error: string }>;
}

/** Request body for S3 bucket ingestion. */
export interface S3IngestBody {
  bucket: string;
  prefix?: string;
  region?: string;
  endpoint_url?: string;
  access_key?: string;
  secret_key?: string;
  no_sign_request?: boolean;
  metadata?: Record<string, unknown>;
  file_types?: string[];
}

/** Response for S3 bucket ingestion. */
export interface S3IngestResponse {
  status: string;
  message: string;
  documents: Document[];
  total: number;
  skipped: string[];
}

/** An S3 ingest job. */
export interface S3Job {
  id: string;
  collection_name: string;
  bucket: string;
  prefix: string;
  region: string;
  status: string;
  total_found: number;
  total_ingested: number;
  total_skipped: number;
  error_message: string | null;
  created_at: string;
  updated_at: string;
}

/** Paginated list of S3 ingest jobs. */
export interface S3JobListResponse {
  jobs: S3Job[];
  total: number;
}

/**
 * Accepted file input types for document upload.
 *
 * - `File` / `Blob` -- browser-native types
 * - `Buffer` / `Uint8Array` -- raw bytes
 * - `{ path: string; name?: string }` -- Node.js file-system path
 */
export type FileInput = File | Blob | Buffer | Uint8Array | { path: string; name?: string };
