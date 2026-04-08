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
  StatusResponse,
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
   * Get all chunks for a document.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   */
  getChunks(collection: string, documentId: string): Promise<DocumentChunkListResponse> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/chunks`,
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
  batchDelete(
    collection: string,
    documentIds: string[],
  ): Promise<BatchDeleteDocumentsResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`,
      { json: { document_ids: documentIds } },
    );
  }

  /**
   * Stream real-time processing progress for a document via SSE.
   *
   * @param collection - The collection name.
   * @param documentId - The document ID.
   * @yields {@link ProgressEvent} objects as they arrive.
   */
  async *streamProgress(
    collection: string,
    documentId: string,
  ): AsyncGenerator<ProgressEvent> {
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
