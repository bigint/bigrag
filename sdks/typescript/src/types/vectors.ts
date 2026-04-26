export interface VectorEntry {
  id: string;
  embedding: number[];
  text?: string;
  metadata?: Record<string, unknown>;
}

export interface UpsertResponse {
  status: string;
  upserted: number;
}

export interface DeleteResponse {
  status: string;
  deleted: number;
}
