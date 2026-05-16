export type CreateCollectionFormValues = {
  chunkOverlap: number;
  chunkSize: number;
  description: string;
  metadataSchemaText: string;
  name: string;
  presetId: string;
  tenantField: string;
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
  metadataSchemaText: "",
  name: "",
  presetId: "",
  tenantField: "",
  vectorStoreProvider: "qdrant",
});

export const defaultCollectionSearchFormValues = (): CollectionSearchFormValues => ({
  mode: "semantic",
  query: "",
  rerank: false,
  topK: 5,
});

const COLLECTION_NAME_RE = /^[a-zA-Z][a-zA-Z0-9_]*$/;

const normalizeCollectionName = (value: string) => value.trim();

const parseMetadataSchema = (value: string): Record<string, unknown> | undefined => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = JSON.parse(trimmed) as unknown;
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
    throw new Error("Metadata schema must be a JSON object");
  }
  return parsed as Record<string, unknown>;
};

export const validateCreateCollectionFormValues = ({
  chunkOverlap,
  chunkSize,
  metadataSchemaText,
  name,
  presetId,
  tenantField,
}: CreateCollectionFormValues): string | undefined => {
  const normalizedName = normalizeCollectionName(name);
  if (!normalizedName) return "Name is required";
  if (!COLLECTION_NAME_RE.test(normalizedName)) {
    return "Name must start with a letter and use only letters, numbers, and underscores";
  }
  if (!presetId) return "Pick an embedding preset first";
  if (chunkSize < 64 || chunkSize > 10000) return "Chunk size must be between 64 and 10000";
  if (chunkOverlap < 0 || chunkOverlap > 5000) return "Chunk overlap must be between 0 and 5000";
  if (chunkOverlap >= chunkSize) return "Chunk overlap must be less than chunk size";
  if (tenantField.trim().length > 64) return "Tenant field must be 64 characters or fewer";
  try {
    parseMetadataSchema(metadataSchemaText);
  } catch (err) {
    return err instanceof Error ? err.message : "Metadata schema must be valid JSON";
  }
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
  metadataSchemaText,
  name,
  presetId,
  tenantField,
  vectorStoreProvider,
}: CreateCollectionFormValues) => ({
  chunk_overlap: chunkOverlap,
  chunk_size: chunkSize,
  description,
  embedding_preset_id: presetId,
  metadata_schema: parseMetadataSchema(metadataSchemaText),
  name: normalizeCollectionName(name),
  tenant_field: tenantField.trim() || null,
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
