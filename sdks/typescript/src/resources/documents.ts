import type { RequestClient } from "../core.js";
import { USER_AGENT } from "../core.js";
import { errorForStatus } from "../errors.js";
import { normalizeFileInput } from "../files.js";
import { parseSSEStream } from "../sse.js";
import type {
  BatchDeleteDocumentsResponse,
  BatchGetDocumentsResponse,
  BatchStatusResponse,
  Document,
  DocumentChunkListResponse,
  DocumentListOptions,
  DocumentListResponse,
  FileInput,
  ProgressEvent,
  S3IngestBody,
  S3IngestResponse,
  S3Job,
  S3JobListResponse,
  StatusResponse,
  UpdateS3JobBody,
} from "../types.js";

/**
 * Resource namespace for document operations within a collection.
 *
 * Access via `client.documents`.
 */
export class DocumentsResource {
  /** @internal */
  constructor(private readonly _client: RequestClient) {}

  /**
   * Upload a single document to a collection.
   *
   * @param collection - The target collection name.
   * @param file - The file to upload (File, Blob, Buffer, Uint8Array, or path object).
   * @param metadata - Optional metadata to attach to the document.
   */
  async upload(
    collection: string,
    file: FileInput,
    metadata?: Record<string, unknown>,
  ): Promise<Document> {
    const form = new FormData();
    const { blob, name } = await normalizeFileInput(file);
    form.append("file", blob, name);
    if (metadata) {
      form.append("metadata", JSON.stringify(metadata));
    }
    return this._client._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/documents`,
      form,
    );
  }

  /**
   * Upload multiple documents in a single request.
   *
   * @param collection - The target collection name.
   * @param files - Array of files to upload.
   * @param metadata - Optional metadata to attach to all documents.
   */
  async batchUpload(
    collection: string,
    files: FileInput[],
    metadata?: Record<string, unknown>,
  ): Promise<DocumentListResponse> {
    const form = new FormData();
    for (const file of files) {
      const { blob, name } = await normalizeFileInput(file);
      form.append("files", blob, name);
    }
    if (metadata) {
      form.append("metadata", JSON.stringify(metadata));
    }
    return this._client._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/upload`,
      form,
    );
  }

  /**
   * List documents in a collection with optional filtering and pagination.
   *
   * @param collection - The collection name.
   * @param options - Optional filters such as `status`, `limit`, and `offset`.
   */
  list(collection: string, options?: DocumentListOptions): Promise<DocumentListResponse> {
    const params: Record<string, string> = {};
    if (options?.status) params.status = options.status;
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents`,
      { params },
    );
  }

  /**
   * Retrieve a single document by ID.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   */
  get(collection: string, documentId: string): Promise<Document> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  /**
   * Delete a document by ID.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   */
  delete(collection: string, documentId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  /**
   * Trigger reprocessing of a document.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   */
  reprocess(collection: string, documentId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/reprocess`,
    );
  }

  /**
   * Get chunks for a document with pagination.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   * @param options - Optional limit and offset for pagination.
   */
  getChunks(
    collection: string,
    documentId: string,
    options?: { limit?: number; offset?: number },
  ): Promise<DocumentChunkListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/chunks`,
      { params },
    );
  }

  /**
   * Build the URL for downloading the original document file.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   * @returns The fully-qualified URL including an auth token query parameter when applicable.
   */
  getFileUrl(collection: string, documentId: string): string {
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/file`;
    if (this._client.apiKey) {
      return `${this._client.baseUrl}${path}?token=${encodeURIComponent(this._client.apiKey)}`;
    }
    return `${this._client.baseUrl}${path}`;
  }

  /**
   * Get the processing status of multiple documents at once.
   *
   * @param collection - The collection name.
   * @param documentIds - Array of document IDs.
   */
  batchGetStatus(collection: string, documentIds: string[]): Promise<BatchStatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/status`,
      { json: { document_ids: documentIds } },
    );
  }

  /**
   * Retrieve multiple documents at once.
   *
   * @param collection - The collection name.
   * @param documentIds - Array of document IDs.
   */
  batchGet(collection: string, documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/get`,
      { json: { document_ids: documentIds } },
    );
  }

  /**
   * Delete multiple documents at once.
   *
   * @param collection - The collection name.
   * @param documentIds - Array of document IDs.
   */
  batchDelete(collection: string, documentIds: string[]): Promise<BatchDeleteDocumentsResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`,
      { json: { document_ids: documentIds } },
    );
  }

  /**
   * List objects in an S3 bucket and ingest supported files.
   *
   * @param collection - The target collection name.
   * @param body - S3 bucket, prefix, credentials, and optional metadata.
   */
  ingestS3(collection: string, body: S3IngestBody): Promise<S3IngestResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/s3`,
      {
        json: body,
      },
    );
  }

  /**
   * Retrieve a document by ID (without specifying collection).
   *
   * @param documentId - The document ID.
   */
  getById(documentId: string): Promise<Document> {
    return this._client._request("GET", `/v1/documents/${encodeURIComponent(documentId)}`);
  }

  /**
   * Get chunks for a document by ID (without specifying collection).
   *
   * @param documentId - The document ID.
   */
  getChunksById(
    documentId: string,
    options?: { limit?: number; offset?: number },
  ): Promise<DocumentChunkListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request(
      "GET",
      `/v1/documents/${encodeURIComponent(documentId)}/chunks`,
      { params },
    );
  }

  /**
   * List S3 ingest jobs for a collection.
   *
   * @param collection - The collection name.
   */
  listS3Jobs(collection: string): Promise<S3JobListResponse> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs`,
    );
  }

  /**
   * Get a single S3 ingest job by ID.
   *
   * @param collection - The collection name.
   * @param jobId - The job ID.
   */
  getS3Job(collection: string, jobId: string): Promise<S3Job> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
    );
  }

  /**
   * Delete an S3 ingest job.
   *
   * @param collection - The collection name.
   * @param jobId - The job ID.
   */
  deleteS3Job(collection: string, jobId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
    );
  }

  /**
   * Update an S3 ingest job (e.g., change file_types).
   *
   * @param collection - The collection name.
   * @param jobId - The job ID.
   * @param body - Fields to update.
   */
  updateS3Job(collection: string, jobId: string, body: UpdateS3JobBody): Promise<S3Job> {
    return this._client._request(
      "PATCH",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
      { json: body },
    );
  }

  /**
   * Re-sync an S3 ingest job. Restarts ingestion, skipping already-ingested files.
   *
   * @param collection - The collection name.
   * @param jobId - The job ID.
   */
  resyncS3Job(collection: string, jobId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}/resync`,
    );
  }

  /**
   * Stream aggregated progress for multiple documents via SSE.
   *
   * @param collection - The collection name.
   * @param documentIds - Array of document IDs to track.
   * @yields {@link ProgressEvent} objects with batch-level summary.
   */
  async *streamBatchProgress(
    collection: string,
    documentIds: string[],
  ): AsyncGenerator<ProgressEvent> {
    const ids = documentIds.join(",");
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/batch/progress?ids=${encodeURIComponent(ids)}`;
    const tokenParam = this._client.apiKey
      ? `&token=${encodeURIComponent(this._client.apiKey)}`
      : "";
    const url = `${this._client.baseUrl}${path}${tokenParam}`;

    const response = await this._client._fetch(url, {
      method: "GET",
      headers: { "User-Agent": USER_AGENT },
    });

    if (!response.ok) {
      throw errorForStatus(response.status, response.statusText);
    }

    yield* parseSSEStream(response);
  }

  /**
   * Stream real-time processing progress for a document via SSE.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   * @yields {@link ProgressEvent} objects as they arrive.
   */
  async *streamProgress(collection: string, documentId: string): AsyncGenerator<ProgressEvent> {
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/progress`;
    const tokenParam = this._client.apiKey
      ? `?token=${encodeURIComponent(this._client.apiKey)}`
      : "";
    const url = `${this._client.baseUrl}${path}${tokenParam}`;

    const response = await this._client._fetch(url, {
      method: "GET",
      headers: { "User-Agent": USER_AGENT },
    });

    if (!response.ok) {
      throw errorForStatus(response.status, response.statusText);
    }

    yield* parseSSEStream(response);
  }
}
