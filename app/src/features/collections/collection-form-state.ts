export type CreateCollectionFormValues = {
  chunkOverlap: number;
  chunkSize: number;
  description: string;
  name: string;
  presetId: string;
  vectorStoreProvider: "qdrant" | "turbopuffer";
};

export type CollectionSearchMode = "semantic" | "keyword" | "hybrid";

export type CollectionSearchFormValues = {
  mode: CollectionSearchMode;
  query: string;
  rerank: boolean;
  topK: number;
};

export const defaultCreateCollectionFormValues = (): CreateCollectionFormValues => ({
  chunkOverlap: 50,
  chunkSize: 512,
  description: "",
  name: "",
  presetId: "",
  vectorStoreProvider: "qdrant",
});

export const defaultCollectionSearchFormValues = (): CollectionSearchFormValues => ({
  mode: "semantic",
  query: "",
  rerank: false,
  topK: 5,
});

export const slugifyCollectionName = (value: string) =>
  value
    .toLowerCase()
    .replace(/[^a-z0-9_\- ]+/g, "")
    .replace(/\s+/g, "_")
    .slice(0, 48);

export const validateCreateCollectionFormValues = ({
  chunkOverlap,
  chunkSize,
  name,
  presetId,
}: CreateCollectionFormValues): string | undefined => {
  if (!name) return "Name is required";
  if (!presetId) return "Pick an embedding preset first";
  if (chunkSize < 128 || chunkSize > 10000) return "Chunk size must be between 128 and 10000";
  if (chunkOverlap < 0 || chunkOverlap > 5000) return "Chunk overlap must be between 0 and 5000";
  return undefined;
};

export const validateCollectionSearchFormValues = ({
  query,
  topK,
}: CollectionSearchFormValues): string | undefined => {
  if (!query.trim()) return "Query is required";
  if (topK < 1 || topK > 50) return "Top K must be between 1 and 50";
  return undefined;
};

export const createCollectionBodyFromValues = ({
  chunkOverlap,
  chunkSize,
  description,
  name,
  presetId,
  vectorStoreProvider,
}: CreateCollectionFormValues) => ({
  chunk_overlap: chunkOverlap,
  chunk_size: chunkSize,
  description,
  embedding_preset_id: presetId,
  name: slugifyCollectionName(name),
  vector_store_provider: vectorStoreProvider,
});

export const collectionSearchBodyFromValues = ({
  mode,
  query,
  rerank,
  topK,
}: CollectionSearchFormValues) => ({
  query,
  rerank,
  search_mode: mode,
  top_k: topK,
});
