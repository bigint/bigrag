import type { RequestClient } from "../core.js";
import { normalizeFileInput } from "../files.js";
import type {
  BatchDeleteDocumentsResponse,
  BatchGetDocumentsResponse,
  BatchStatusResponse,
  Document,
  DocumentChunkListResponse,
  DocumentListOptions,
  DocumentListResponse,
  FileInput,
  StatusResponse,
  UploadSession,
  UploadSessionCreateRequest,
  UploadSessionFileResponse,
} from "../types.js";

export class DocumentsResource {
  constructor(private readonly _client: RequestClient) {}

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

  createUploadSession(
    collection: string,
    body: UploadSessionCreateRequest,
  ): Promise<UploadSession> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/upload-sessions`,
      { json: { ...body, metadata: body.metadata ?? {} } },
    );
  }

  getUploadSession(collection: string, sessionId: string): Promise<UploadSession> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/upload-sessions/${encodeURIComponent(sessionId)}`,
    );
  }

  async uploadSessionFile(
    collection: string,
    sessionId: string,
    file: FileInput,
    options?: { clientItemId?: string; filename?: string },
  ): Promise<UploadSessionFileResponse> {
    const form = new FormData();
    const { blob, name } = await normalizeFileInput(file);
    if (options?.clientItemId) form.append("client_item_id", options.clientItemId);
    form.append("file", blob, options?.filename ?? name);
    return this._client._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/upload-sessions/${encodeURIComponent(sessionId)}/files`,
      form,
    );
  }

  completeUploadSession(collection: string, sessionId: string): Promise<UploadSession> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/upload-sessions/${encodeURIComponent(sessionId)}/complete`,
    );
  }

  cancelUploadSession(collection: string, sessionId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/upload-sessions/${encodeURIComponent(sessionId)}/cancel`,
    );
  }

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

  async *listAll(
    collection: string,
    options?: Omit<DocumentListOptions, "offset">,
  ): AsyncGenerator<Document> {
    const pageSize = options?.limit ?? 100;
    let offset = 0;
    while (true) {
      const page = await this.list(collection, {
        ...options,
        limit: pageSize,
        offset,
      });
      for (const doc of page.documents) yield doc;
      if (page.documents.length < pageSize) return;
      offset += page.documents.length;
      if (offset >= page.total) return;
    }
  }

  get(collection: string, documentId: string): Promise<Document> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  delete(collection: string, documentId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}`,
    );
  }

  reprocess(collection: string, documentId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/reprocess`,
    );
  }

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

  getFileUrl(collection: string, documentId: string): string {
    const path = `/v1/collections/${encodeURIComponent(collection)}/documents/${encodeURIComponent(documentId)}/file`;
    return `${this._client.baseUrl}${path}`;
  }

  batchGetStatus(collection: string, documentIds: string[]): Promise<BatchStatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/status`,
      { json: { document_ids: documentIds } },
    );
  }

  batchGet(collection: string, documentIds: string[]): Promise<BatchGetDocumentsResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/get`,
      { json: { document_ids: documentIds } },
    );
  }

  batchDelete(collection: string, documentIds: string[]): Promise<BatchDeleteDocumentsResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/batch/delete`,
      { json: { document_ids: documentIds } },
    );
  }

  getById(documentId: string): Promise<Document> {
    return this._client._request("GET", `/v1/documents/${encodeURIComponent(documentId)}`);
  }

  getChunksById(
    documentId: string,
    options?: { limit?: number; offset?: number },
  ): Promise<DocumentChunkListResponse> {
    const params: Record<string, string> = {};
    if (options?.limit !== undefined) params.limit = String(options.limit);
    if (options?.offset !== undefined) params.offset = String(options.offset);
    return this._client._request("GET", `/v1/documents/${encodeURIComponent(documentId)}/chunks`, {
      params,
    });
  }
}
