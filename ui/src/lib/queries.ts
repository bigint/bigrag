import { queryOptions } from "@tanstack/react-query";
import {
  getCollection,
  getHealth,
  getMetrics,
  listCollections,
  listDocuments,
  listEmbeddingModels
} from "@/lib/api";

export const healthQueryOptions = () =>
  queryOptions({
    queryFn: () => getHealth(),
    queryKey: ["health"]
  });

export const collectionsQueryOptions = () =>
  queryOptions({
    queryFn: () => listCollections(),
    queryKey: ["collections"]
  });

export const collectionQueryOptions = (name: string) =>
  queryOptions({
    queryFn: () => getCollection(name),
    queryKey: ["collection", name]
  });

export const documentsQueryOptions = (collectionName: string, status?: string) =>
  queryOptions({
    queryFn: () => listDocuments(collectionName, status),
    queryKey: ["documents", collectionName, status]
  });

export const embeddingModelsQueryOptions = () =>
  queryOptions({
    queryFn: () => listEmbeddingModels(),
    queryKey: ["embedding-models"]
  });

export const metricsQueryOptions = () =>
  queryOptions({
    queryFn: () => getMetrics(),
    queryKey: ["metrics"],
    refetchInterval: 10_000
  });
