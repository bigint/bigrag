import { useEffect, useState } from "react";
import { ALL_FILE_TYPES, getAllowedFileTypes } from "@/lib/file-types";
import type { Collection } from "@/types/bigrag";

export type SearchMode = "semantic" | "keyword" | "hybrid";

export const useCollectionSettingsDraft = (collection: Collection | undefined) => {
  const [description, setDescription] = useState("");
  const [topK, setTopK] = useState(10);
  const [searchMode, setSearchMode] = useState<SearchMode>("semantic");
  const [rerankingEnabled, setRerankingEnabled] = useState(false);
  const [multimodalEnabled, setMultimodalEnabled] = useState(false);
  const [multimodalEnrichmentEnabled, setMultimodalEnrichmentEnabled] = useState(false);
  const [embeddingKeyDraft, setEmbeddingKeyDraft] = useState("");
  const [allowedTypes, setAllowedTypes] = useState<Set<string>>(new Set(ALL_FILE_TYPES));

  useEffect(() => {
    if (!collection) return;
    setDescription(collection.description);
    setTopK(collection.default_top_k);
    setSearchMode(collection.default_search_mode);
    setRerankingEnabled(collection.reranking_enabled);
    setMultimodalEnabled(collection.multimodal_enabled);
    setMultimodalEnrichmentEnabled(collection.multimodal_enrichment_enabled);
    const stored = getAllowedFileTypes(collection.metadata);
    setAllowedTypes(new Set(stored.length ? stored : ALL_FILE_TYPES));
  }, [collection]);

  const toggleType = (t: string) => {
    setAllowedTypes((prev) => {
      const next = new Set(prev);
      if (next.has(t)) {
        next.delete(t);
      } else {
        next.add(t);
      }
      return next;
    });
  };

  const toggleCategory = (types: string[]) => {
    const allSelected = types.every((t) => allowedTypes.has(t));
    setAllowedTypes((prev) => {
      const next = new Set(prev);
      for (const t of types) {
        if (allSelected) {
          next.delete(t);
        } else {
          next.add(t);
        }
      }
      return next;
    });
  };

  const toggleMultimodal = (enabled: boolean) => {
    setMultimodalEnabled(enabled);
    if (!enabled) setMultimodalEnrichmentEnabled(false);
  };

  const toggleMultimodalEnrichment = (enabled: boolean) => {
    setMultimodalEnrichmentEnabled(enabled);
    if (enabled) setMultimodalEnabled(true);
  };

  const fileTypesDraft = Array.from(allowedTypes).sort();
  const storedTypes = collection ? getAllowedFileTypes(collection.metadata) : [];
  const initialTypes = (storedTypes.length ? storedTypes : ALL_FILE_TYPES).slice().sort();

  const defaultsDirty = collection
    ? description !== collection.description ||
      topK !== collection.default_top_k ||
      searchMode !== collection.default_search_mode ||
      rerankingEnabled !== collection.reranking_enabled
    : false;
  const multimodalDirty = collection
    ? multimodalEnabled !== collection.multimodal_enabled ||
      multimodalEnrichmentEnabled !== collection.multimodal_enrichment_enabled
    : false;
  const fileTypesDirty = fileTypesDraft.join(",") !== initialTypes.join(",");

  return {
    description,
    setDescription,
    topK,
    setTopK,
    searchMode,
    setSearchMode,
    rerankingEnabled,
    setRerankingEnabled,
    multimodalEnabled,
    multimodalEnrichmentEnabled,
    toggleMultimodal,
    toggleMultimodalEnrichment,
    embeddingKeyDraft,
    setEmbeddingKeyDraft,
    allowedTypes,
    setAllowedTypes,
    toggleType,
    toggleCategory,
    fileTypesDraft,
    defaultsDirty,
    multimodalDirty,
    fileTypesDirty,
  };
};
