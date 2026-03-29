"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Inbox, Plus, Trash2 } from "lucide-react";
import Link from "next/link";
import { useState } from "react";
import { createCollection, deleteCollection, listEmbeddingModels } from "@/lib/api";
import { collectionsQueryOptions, embeddingModelsQueryOptions } from "@/lib/queries";
import { timeAgo } from "@/lib/utils";

const CollectionsPage = () => {
  const queryClient = useQueryClient();
  const collectionsQuery = useQuery(collectionsQueryOptions());
  const modelsQuery = useQuery(embeddingModelsQueryOptions());
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [selectedModel, setSelectedModel] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [baseUrl, setBaseUrl] = useState("");
  const [error, setError] = useState("");

  const selectedProvider = modelsQuery.data?.models.find(
    (m) => `${m.provider}/${m.model}` === selectedModel
  )?.provider;
  const needsApiKey = selectedProvider === "openai" || selectedProvider === "cohere" || selectedProvider === "custom";
  const needsBaseUrl = selectedProvider === "ollama" || selectedProvider === "custom";

  const createMutation = useMutation({
    mutationFn: () => {
      const model = modelsQuery.data?.models.find(
        (m) => `${m.provider}/${m.model}` === selectedModel
      );
      return createCollection({
        name,
        description,
        ...(model
          ? {
              embedding_provider: model.provider,
              embedding_model: model.model,
              dimension: model.dimension
            }
          : {}),
        ...(apiKey ? { embedding_api_key: apiKey } : {}),
        ...(baseUrl ? { embedding_base_url: baseUrl } : {}),
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["collections"] });
      setShowCreate(false);
      setName("");
      setDescription("");
      setApiKey("");
      setBaseUrl("");
      setError("");
    },
    onError: (err) => setError(err.message)
  });

  const deleteMutation = useMutation({
    mutationFn: deleteCollection,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["collections"] })
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
          <h2 className="mb-4 text-sm font-medium text-text">Create Collection</h2>
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
              <option value="">Default embedding model</option>
              {models.map((m) => (
                <option key={`${m.provider}/${m.model}`} value={`${m.provider}/${m.model}`}>
                  {m.model} ({m.provider}, {m.dimension}d) — {m.description}
                </option>
              ))}
            </select>
            {needsApiKey && (
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  API Key {selectedProvider === "openai" ? "(OpenAI)" : selectedProvider === "cohere" ? "(Cohere)" : ""}
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  type="password"
                  value={apiKey}
                />
                <p className="mt-1 text-[11px] text-text-dim">
                  Required. Stored securely per collection.
                </p>
              </div>
            )}
            {needsBaseUrl && (
              <div>
                <label className="mb-1 block text-xs text-text-muted">
                  Base URL {selectedProvider === "ollama" ? "(Ollama)" : "(API endpoint)"}
                </label>
                <input
                  className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
                  onChange={(e) => setBaseUrl(e.target.value)}
                  placeholder={selectedProvider === "ollama" ? "http://localhost:11434" : "https://api.example.com/v1"}
                  type="url"
                  value={baseUrl}
                />
              </div>
            )}
            {error && (
              <p className="text-sm text-danger">{error}</p>
            )}
            <div className="flex gap-2">
              <button
                className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white hover:bg-accent/90 disabled:opacity-50"
                disabled={!name || createMutation.isPending || (needsApiKey && !apiKey)}
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
            <div className="animate-pulse rounded-lg border border-border bg-bg-card p-5" key={i}>
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
                <p className="mb-2 text-xs text-text-muted">{col.description}</p>
              )}
              <p className="text-xs text-text-muted">
                <span className="font-mono">{col.document_count}</span> documents
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
