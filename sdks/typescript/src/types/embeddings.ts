export interface EmbeddingModelInfo {
  provider: string;
  model: string;
  dimension: number;
  description: string;
}

export interface EmbeddingModelListResponse {
  models: EmbeddingModelInfo[];
}
