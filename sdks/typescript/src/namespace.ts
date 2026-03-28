import type { BigRAG } from "./client.js";
import type {
  UpsertRow,
  PatchRow,
  QueryOptions,
  QueryResponse,
  WriteResponse,
  NamespaceMetadata,
  RecallResult,
  Filter,
} from "./types.js";

/**
 * Handle for performing operations on a single bigRAG namespace.
 *
 * Obtain an instance via `client.namespace("name")`.
 */
export class Namespace {
  constructor(
    private readonly client: BigRAG,
    public readonly name: string,
  ) {}

  /**
   * Upsert rows into the namespace. Creates or replaces rows by ID.
   *
   * @param rows - Rows to upsert. Each must have an `id` and optionally a `vector` and attributes.
   * @param options - Optional distance metric and schema.
   */
  async upsert(
    rows: UpsertRow[],
    options?: {
      distanceMetric?: string;
      schema?: Record<string, unknown>;
    },
  ): Promise<WriteResponse> {
    const body: Record<string, unknown> = {
      upsert_rows: rows,
    };
    if (options?.distanceMetric) {
      body.distance_metric = options.distanceMetric;
    }
    if (options?.schema) {
      body.schema = options.schema;
    }
    return this.client._request<WriteResponse>(
      "POST",
      `/v2/namespaces/${encodeURIComponent(this.name)}`,
      body,
    );
  }

  /**
   * Query the namespace for similar vectors or full-text matches.
   *
   * @param options - Query parameters including ranking strategy, top_k, filters, etc.
   */
  async query(options: QueryOptions): Promise<QueryResponse> {
    const body: Record<string, unknown> = {
      rank_by: options.rankBy,
      top_k: options.topK,
    };
    if (options.filters !== undefined) {
      body.filters = options.filters;
    }
    if (options.includeAttributes !== undefined) {
      body.include_attributes = options.includeAttributes;
    }
    if (options.includeVectors !== undefined) {
      body.include_vectors = options.includeVectors;
    }
    return this.client._request<QueryResponse>(
      "POST",
      `/v2/namespaces/${encodeURIComponent(this.name)}/query`,
      body,
    );
  }

  /**
   * Delete rows by their IDs.
   *
   * @param ids - Array of row IDs to delete.
   */
  async delete(ids: (string | number)[]): Promise<WriteResponse> {
    const body = {
      delete_rows: ids,
    };
    return this.client._request<WriteResponse>(
      "POST",
      `/v2/namespaces/${encodeURIComponent(this.name)}`,
      body,
    );
  }

  /**
   * Delete the entire namespace and all its data.
   */
  async deleteAll(): Promise<void> {
    await this.client._request<void>(
      "DELETE",
      `/v2/namespaces/${encodeURIComponent(this.name)}`,
    );
  }

  /**
   * Delete rows matching a filter expression.
   *
   * @param filter - Filter expression to match rows for deletion.
   * @param options - Optional safety constraints.
   */
  async deleteByFilter(
    filter: Filter,
    options?: {
      maxAffected?: number;
      allowPartial?: boolean;
    },
  ): Promise<WriteResponse> {
    const body: Record<string, unknown> = {
      delete_by_filter: filter,
    };
    if (options?.maxAffected !== undefined) {
      body.max_affected = options.maxAffected;
    }
    if (options?.allowPartial !== undefined) {
      body.allow_partial = options.allowPartial;
    }
    return this.client._request<WriteResponse>(
      "POST",
      `/v2/namespaces/${encodeURIComponent(this.name)}`,
      body,
    );
  }

  /**
   * Patch (partially update) existing rows.
   *
   * @param rows - Rows to patch. Each must have an `id` and the attributes to update.
   */
  async patch(rows: PatchRow[]): Promise<WriteResponse> {
    const body = {
      patch_rows: rows,
    };
    return this.client._request<WriteResponse>(
      "POST",
      `/v2/namespaces/${encodeURIComponent(this.name)}`,
      body,
    );
  }

  /**
   * Get metadata about this namespace.
   */
  async metadata(): Promise<NamespaceMetadata> {
    return this.client._request<NamespaceMetadata>(
      "GET",
      `/v1/namespaces/${encodeURIComponent(this.name)}/metadata`,
    );
  }

  /**
   * Get the schema for this namespace.
   */
  async schema(): Promise<Record<string, unknown>> {
    return this.client._request<Record<string, unknown>>(
      "GET",
      `/v1/namespaces/${encodeURIComponent(this.name)}/schema`,
    );
  }

  /**
   * Update the schema for this namespace.
   *
   * @param schema - The new schema definition.
   */
  async updateSchema(schema: Record<string, unknown>): Promise<void> {
    await this.client._request<void>(
      "PUT",
      `/v1/namespaces/${encodeURIComponent(this.name)}/schema`,
      schema,
    );
  }

  /**
   * Run a recall debug test against this namespace.
   *
   * @param options - Optional parameters for the recall test.
   */
  async recall(options?: {
    num?: number;
    topK?: number;
  }): Promise<RecallResult> {
    const body: Record<string, unknown> = {};
    if (options?.num !== undefined) {
      body.num = options.num;
    }
    if (options?.topK !== undefined) {
      body.top_k = options.topK;
    }
    return this.client._request<RecallResult>(
      "POST",
      `/v1/namespaces/${encodeURIComponent(this.name)}/_debug/recall`,
      body,
    );
  }
}
