import { Link, useNavigate } from "@tanstack/react-router";
import { toast } from "sonner";
import { QueryError } from "@/components/ui/query-error";
import { Spinner } from "@/components/ui/spinner";
import { AllowedFileTypesCard } from "@/features/collections/collection-settings/allowed-file-types-card";
import { DangerZoneCard } from "@/features/collections/collection-settings/danger-zone-card";
import { DocumentElementsCard } from "@/features/collections/collection-settings/document-elements-card";
import { EmbeddingKeyCard } from "@/features/collections/collection-settings/embedding-key-card";
import { RetrievalDefaultsCard } from "@/features/collections/collection-settings/retrieval-defaults-card";
import { useCollectionSettingsDraft } from "@/features/collections/collection-settings/use-collection-settings-draft";
import {
  useCollection,
  useDeleteCollection,
  useTruncateCollection,
  useUpdateCollection,
} from "@/hooks/use-collections";
import { ALL_FILE_TYPES } from "@/lib/file-types";

export const CollectionSettings = ({ name }: { name: string }) => {
  const navigate = useNavigate();
  const { data: collection, error, isError, isPending, refetch } = useCollection(name);
  const update = useUpdateCollection(name);
  const truncate = useTruncateCollection(name);
  const remove = useDeleteCollection();
  const draft = useCollectionSettingsDraft(collection);

  if (isError) {
    return (
      <QueryError
        className="p-4"
        error={error}
        onRetry={() => refetch()}
        title="Couldn't load collection settings"
      />
    );
  }

  if (isPending || !collection) {
    return (
      <div className="flex justify-center py-8">
        <Spinner />
      </div>
    );
  }

  const saveDefaults = async () => {
    try {
      await update.mutateAsync({
        description: draft.description,
        default_top_k: draft.topK,
        default_search_mode: draft.searchMode,
        reranking_enabled: draft.rerankingEnabled,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const saveMultimodal = async () => {
    try {
      await update.mutateAsync({
        multimodal_enabled: draft.multimodalEnabled,
        multimodal_enrichment_enabled: draft.multimodalEnrichmentEnabled,
      });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const saveEmbeddingKey = async () => {
    const trimmed = draft.embeddingKeyDraft.trim();
    if (!trimmed) return;
    try {
      await update.mutateAsync({ embedding_api_key: trimmed });
      draft.setEmbeddingKeyDraft("");
      toast.success("Embedding API key updated");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const saveFileTypes = async () => {
    const list = draft.fileTypesDraft;
    const unrestricted = list.length === ALL_FILE_TYPES.length;
    try {
      await update.mutateAsync({
        metadata: {
          ...(collection.metadata ?? {}),
          allowed_file_types: unrestricted ? [] : list,
        },
      });
      toast.success(
        unrestricted
          ? "All file types allowed"
          : `Restricted to ${list.length} type${list.length === 1 ? "" : "s"}`,
      );
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Save failed");
    }
  };

  const embeddingKeyStatus = collection.has_api_key
    ? collection.embedding_preset_id
      ? "Using preset key"
      : "Collection key saved"
    : "No key saved";

  return (
    <div className="flex flex-col gap-6">
      <div>
        <Link
          to="/collections/$name/documents"
          params={{ name }}
          className="text-sm text-muted-foreground hover:text-foreground"
        >
          ← Back to collection
        </Link>
      </div>

      <RetrievalDefaultsCard
        description={draft.description}
        onDescriptionChange={draft.setDescription}
        topK={draft.topK}
        onTopKChange={draft.setTopK}
        searchMode={draft.searchMode}
        onSearchModeChange={draft.setSearchMode}
        rerankingEnabled={draft.rerankingEnabled}
        onRerankingChange={draft.setRerankingEnabled}
        dirty={draft.defaultsDirty}
        saving={update.isPending}
        onSave={saveDefaults}
      />

      <EmbeddingKeyCard
        status={embeddingKeyStatus}
        value={draft.embeddingKeyDraft}
        onChange={draft.setEmbeddingKeyDraft}
        saving={update.isPending}
        onSave={saveEmbeddingKey}
      />

      <AllowedFileTypesCard
        allowedTypes={draft.allowedTypes}
        onSelectAll={() => draft.setAllowedTypes(new Set(ALL_FILE_TYPES))}
        onClearAll={() => draft.setAllowedTypes(new Set())}
        onToggleType={draft.toggleType}
        onToggleCategory={draft.toggleCategory}
        dirty={draft.fileTypesDirty}
        saving={update.isPending}
        onSave={saveFileTypes}
      />

      <DocumentElementsCard
        multimodalEnabled={draft.multimodalEnabled}
        multimodalEnrichmentEnabled={draft.multimodalEnrichmentEnabled}
        onToggleMultimodal={draft.toggleMultimodal}
        onToggleEnrichment={draft.toggleMultimodalEnrichment}
        dirty={draft.multimodalDirty}
        saving={update.isPending}
        onSave={saveMultimodal}
      />

      <DangerZoneCard
        collectionName={collection.name}
        truncatePending={truncate.isPending}
        onTruncate={async () => {
          await truncate.mutateAsync();
        }}
        deletePending={remove.isPending}
        onDelete={async () => {
          await remove.mutateAsync(collection.name);
          navigate({ to: "/collections", replace: true });
        }}
      />
    </div>
  );
};
