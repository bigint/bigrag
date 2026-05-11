import type { CollectionStatsResponse, Collection as SdkCollection } from "@rag.computer/client";

export type Collection = Omit<SdkCollection, "default_search_mode"> & {
  embedding_preset_id: string | null;
  default_search_mode: "semantic" | "keyword" | "hybrid";
};

export type CollectionStats = CollectionStatsResponse;
