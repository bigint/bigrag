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

export class DocumentsResource {
  constructor(private readonly _client: RequestClient) {}

  async upload(
    collection: string,
    file: FileInput,
    metadata?: Record<string, unknown>,
    options?: { onUploadProgress?: (ev: { loaded: number; total: number }) => void },
  ): Promise<Document> {
    const form = new FormData();
    const { blob, name } = await normalizeFileInput(file);
    form.append("file", blob, name);
    if (metadata) {
      form.append("metadata", JSON.stringify(metadata));
    }
    if (options?.onUploadProgress && typeof XMLHttpRequest !== "undefined") {
      return this._uploadWithProgress(collection, form, options.onUploadProgress);
    }
    return this._client._requestFormData(
      `/v1/collections/${encodeURIComponent(collection)}/documents`,
      form,
    );
  }

  private _uploadWithProgress(
    collection: string,
    form: FormData,
    onProgress: (ev: { loaded: number; total: number }) => void,
  ): Promise<Document> {
    return new Promise<Document>((resolve, reject) => {
      const xhr = new XMLHttpRequest();
      const url = `${this._client.baseUrl}/v1/collections/${encodeURIComponent(collection)}/documents`;
      xhr.open("POST", url);
      if (this._client.apiKey) {
        xhr.setRequestHeader("Authorization", `Bearer ${this._client.apiKey}`);
      }
      xhr.upload.onprogress = (ev) => {
        if (ev.lengthComputable) {
          onProgress({ loaded: ev.loaded, total: ev.total });
        }
      };
      xhr.onload = () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          try {
            resolve(JSON.parse(xhr.responseText) as Document);
          } catch (err) {
            reject(err instanceof Error ? err : new Error(String(err)));
          }
        } else {
          reject(errorForStatus(xhr.status, xhr.responseText || xhr.statusText));
        }
      };
      xhr.onerror = () => reject(new Error("Network error during upload"));
      xhr.send(form);
    });
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
    if (this._client.apiKey) {
      return `${this._client.baseUrl}${path}?token=${encodeURIComponent(this._client.apiKey)}`;
    }
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

  ingestS3(collection: string, body: S3IngestBody): Promise<S3IngestResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/documents/s3`,
      {
        json: body,
      },
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

  listS3Jobs(collection: string): Promise<S3JobListResponse> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs`,
    );
  }

  getS3Job(collection: string, jobId: string): Promise<S3Job> {
    return this._client._request(
      "GET",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
    );
  }

  deleteS3Job(collection: string, jobId: string): Promise<StatusResponse> {
    return this._client._request(
      "DELETE",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
    );
  }

  updateS3Job(collection: string, jobId: string, body: UpdateS3JobBody): Promise<S3Job> {
    return this._client._request(
      "PATCH",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}`,
      { json: body },
    );
  }

  resyncS3Job(collection: string, jobId: string): Promise<StatusResponse> {
    return this._client._request(
      "POST",
      `/v1/collections/${encodeURIComponent(collection)}/s3-jobs/${encodeURIComponent(jobId)}/resync`,
    );
  }

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
