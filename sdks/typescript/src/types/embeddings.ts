/** Information about an available embedding model. */
export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

/** Response listing all available embedding models. */
export interface EmbeddingModelListResponse {
  models: EmbeddingModelInfo[];
}
