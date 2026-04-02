"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Inbox, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { getClient } from "@/lib/client";
import {
  collectionsQueryOptions,
  embeddingModelsQueryOptions
} from "@/lib/queries";
import { timeAgo } from "@/lib/utils";

const CollectionsPage = () => {
  const queryClient = useQueryClient();
  const collectionsQuery = useQuery(collectionsQueryOptions());
  const modelsQuery = useQuery(embeddingModelsQueryOptions());
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedModel, setSelectedModel] = useState("openai/text-embedding-3-small");
  const [apiKey, setApiKey] = useState("");
  const [chunkSize, setChunkSize] = useState(512);
  const [chunkOverlap, setChunkOverlap] = useState(50);
  const [rerankEnabled, setRerankEnabled] = useState(false);
  const [rerankModel, setRerankModel] = useState("rerank-v3.5");
  const [rerankApiKey, setRerankApiKey] = useState("");
  const [error, setError] = useState("");

  const selectedModelInfo = modelsQuery.data?.models.find(
    (m) => `${m.provider}/${m.model}` === selectedModel
  );
  const selectedProvider = selectedModelInfo?.provider;

  const createMutation = useMutation({
    mutationFn: () =>
      getClient().createCollection({
        name,
        description,
        chunk_size: chunkSize,
        chunk_overlap: chunkOverlap,
        ...(selectedModelInfo
          ? {
              dimension: selectedModelInfo.dimension,
              embedding_model: selectedModelInfo.model,
              embedding_provider: selectedModelInfo.provider
            }
          : {}),
        ...(apiKey ? { embedding_api_key: apiKey } : {}),
        ...(rerankEnabled ? {
          reranking_enabled: true,
          reranking_model: rerankModel,
          ...(rerankApiKey ? { reranking_api_key: rerankApiKey } : {})
        } : {})
      }),
    onError: (err) => setError(err.message),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      setShowCreate(false);
      setName("");
      setDescription("");
      setApiKey("");
      setChunkSize(512);
      setChunkOverlap(50);
      setRerankEnabled(false);
      setRerankModel("rerank-v3.5");
      setRerankApiKey("");
      setError("");
    }
  });

  const deleteMutation = useMutation({
    mutationFn: (name: string) => getClient().deleteCollection(name),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["collections"] })
  });

  const collections = collectionsQuery.data?.collections ?? [];
  const models = modelsQuery.data?.models ?? [];

  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-xl font-semibold text-text">Collections</h1>
        <button
          className="flex items-center gap-1.5 rounded-md bg-accent px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-accent/90"
          onClick={() => setShowCreate(!showCreate)}
          type="button"
        >
          <Plus className="size-4" />
          New Collection
        </button>
      </div>

      {showCreate && (
        <div className="mb-6 rounded-lg border border-border bg-bg-card p-5">
          <h2 className="mb-4 text-sm font-medium text-text">
            Create Collection
          </h2>
          <div className="space-y-3">
            <input
              className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
              onChange={(e) => setName(e.target.value)}
              placeholder="Collection name (e.g. research_papers)"
              value={name}
            />
            <input
              className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
              onChange={(e) => setDescription(e.target.value)}
              placeholder="Description (optional)"
              value={description}
            />
            <select
              className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
              onChange={(e) => setSelectedModel(e.target.value)}
              value={selectedModel}
            >
              {models.map((m) => (
                <option
                  key={`${m.provider}/${m.model}`}
                  value={`${m.provider}/${m.model}`}
                >
                  {m.model} ({m.provider}, {m.dimension}d) — {m.description}
                </option>
              ))}
            </select>
            <div>
              <label className="mb-1 block text-xs text-text-muted">
                API Key{" "}
                {selectedProvider === "openai"
                  ? "(OpenAI)"
                  : "(Cohere)"}
              </label>
              <input
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                onChange={(e) => setApiKey(e.target.value)}
                placeholder={
                  selectedProvider === "openai" ? "sk-..." : "Enter Cohere API key"
                }
                type="password"
                value={apiKey}
              />
              <p className="mt-1 text-[11px] text-text-dim">
                Required. Stored securely per collection.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  Chunk Size (tokens)
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
                  max={10000}
                  min={64}
                  onChange={(e) => setChunkSize(Number(e.target.value))}
                  type="number"
                  value={chunkSize}
                />
              </div>
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  Chunk Overlap (tokens)
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
                  max={5000}
                  min={0}
                  onChange={(e) => setChunkOverlap(Number(e.target.value))}
                  type="number"
                  value={chunkOverlap}
                />
              </div>
            </div>
            <div className="space-y-2 rounded-md border border-border p-3">
              <div className="flex items-center gap-2">
                <input
                  checked={rerankEnabled}
                  id="rerank-toggle"
                  onChange={(e) => setRerankEnabled(e.target.checked)}
                  type="checkbox"
                />
                <label className="text-sm text-text-muted" htmlFor="rerank-toggle">
                  Enable reranking (Cohere)
                </label>
              </div>
              {rerankEnabled && (
                <div className="space-y-2 pl-5">
                  <div>
                    <label className="mb-1 block text-xs text-text-muted">Reranking Model</label>
                    <select
                      className="w-full rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text focus:border-border-hover focus:outline-none"
                      onChange={(e) => setRerankModel(e.target.value)}
                      value={rerankModel}
                    >
                      <option value="rerank-v3.5">rerank-v3.5</option>
                      <option value="rerank-english-v3.0">rerank-english-v3.0</option>
                      <option value="rerank-multilingual-v3.0">rerank-multilingual-v3.0</option>
                    </select>
                  </div>
                  <div>
                    <label className="mb-1 block text-xs text-text-muted">Cohere API Key (for reranking)</label>
                    <input
                      className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                      onChange={(e) => setRerankApiKey(e.target.value)}
                      placeholder="Uses embedding key as fallback"
                      type="password"
                      value={rerankApiKey}
                    />
                  </div>
                </div>
              )}
            </div>
            {error && <p className="text-sm text-danger">{error}</p>}
            <div className="flex gap-2">
              <button
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
                disabled={
                  !name || !apiKey || createMutation.isPending
                }
                onClick={() => createMutation.mutate()}
                type="button"
              >
                {createMutation.isPending ? "Creating..." : "Create"}
              </button>
              <button
                className="rounded-md border border-border px-4 py-2 text-sm text-text-muted hover:bg-bg-hover"
                onClick={() => setShowCreate(false)}
                type="button"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {collectionsQuery.isLoading && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {Array.from({ length: 6 }).map((_, i) => (
            <div
              className="animate-pulse rounded-lg border border-border bg-bg-card p-5"
              key={i}
            >
              <div className="mb-3 h-4 w-40 rounded bg-bg-hover" />
              <div className="mt-2 h-3.5 w-28 rounded bg-bg-hover" />
            </div>
          ))}
        </div>
      )}

      {!collectionsQuery.isLoading && collections.length === 0 && (
        <div className="flex flex-col items-center justify-center py-20">
          <Inbox className="mb-3 size-10 text-text-dim" />
          <p className="text-sm text-text-muted">No collections yet</p>
          <p className="mt-1 text-xs text-text-dim">
            Create a collection to start uploading documents
          </p>
        </div>
      )}

      {collections.length > 0 && (
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
          {collections.map((col) => (
            <div
              className="group relative rounded-lg border border-border bg-bg-card p-5 transition-colors hover:border-border-hover hover:bg-bg-hover/30"
              key={col.id}
            >
              <Link
                className="absolute inset-0 rounded-lg"
                href={`/collections/${encodeURIComponent(col.name)}`}
              />
              <div className="mb-2 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database className="size-4 text-text-dim" />
                  <span className="font-mono text-sm font-medium text-text">
                    {col.name}
                  </span>
                </div>
                <button
                  className="relative z-10 rounded-md p-1 text-text-dim opacity-0 transition-all hover:bg-danger/10 hover:text-danger group-hover:opacity-100"
                  onClick={() => {
                    if (confirm(`Delete collection "${col.name}"?`))
                      deleteMutation.mutate(col.name);
                  }}
                  type="button"
                >
                  <Trash2 className="size-3.5" />
                </button>
              </div>
              {col.description && (
                <p className="mb-2 text-xs text-text-muted">
                  {col.description}
                </p>
              )}
              <p className="text-xs text-text-muted">
                <span className="font-mono">{col.document_count}</span>{" "}
                documents
                <span className="mx-1.5 text-text-dim">&middot;</span>
                <span className="font-mono">{col.embedding_model}</span>
              </p>
              <p className="mt-1 text-xs text-text-dim">
                Updated {timeAgo(col.updated_at)}
              </p>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default CollectionsPage;
