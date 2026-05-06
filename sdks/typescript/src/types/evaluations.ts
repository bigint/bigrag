export interface EvalCase {
  query: string;
  relevant_ids: string[];
  top_k?: number | null;
}

export interface EvalBody {
  collection: string;
  cases: EvalCase[];
  top_k?: number;
  search_mode?: "semantic" | "keyword" | "hybrid";
}

export interface EvalPerCase {
  query: string;
  hit_ids: string[];
  expected_ids: string[];
  recall_at_k: number;
  reciprocal_rank: number;
  ndcg_at_k: number;
}

export interface EvalResponse {
  collection: string;
  total_cases: number;
  recall_at_k_avg: number;
  mrr: number;
  ndcg_at_k_avg: number;
  per_case: EvalPerCase[];
}
