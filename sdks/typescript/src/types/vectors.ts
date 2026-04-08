/** A vector entry for upsert operations. */
export interface VectorEntry {
  id: string;
  embedding: number[];
  text?: string;
  metadata?: Record<string, unknown>;
}

/** Response for a vector upsert operation. */
export interface UpsertResponse {
  status: string;
  upserted: number;
}

/** Response for a vector delete operation. */
export interface DeleteResponse {
  status: string;
  deleted: number;
}
