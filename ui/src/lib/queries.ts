import { queryOptions } from "@tanstack/react-query";
import { getClient } from "./client";

export const healthQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().health(),
    queryKey: ["health"]
  });

export const collectionsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().listCollections(),
    queryKey: ["collections"]
  });

export const collectionQueryOptions = (name: string) =>
  queryOptions({
    queryFn: () => getClient().getCollection(name),
    queryKey: ["collection", name]
  });

export const documentsQueryOptions = (
  collectionName: string,
  status?: string
) =>
  queryOptions({
    queryFn: () =>
      getClient().listDocuments(
        collectionName,
        status ? { status } : undefined
      ),
    queryKey: ["documents", collectionName, status]
  });

export const embeddingModelsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().listEmbeddingModels(),
    queryKey: ["embedding-models"]
  });

export const metricsQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().getMetrics(),
    queryKey: ["metrics"],
    refetchInterval: 10_000
  });

export const webhooksQueryOptions = () =>
  queryOptions({
    queryFn: () => getClient().listWebhooks(),
    queryKey: ["webhooks"]
  });

export const webhookDeliveriesQueryOptions = (webhookId: string) =>
  queryOptions({
    queryFn: () => getClient().listWebhookDeliveries(webhookId),
    queryKey: ["webhook-deliveries", webhookId]
  });

export const analyticsQueryOptions = (collectionName: string) =>
  queryOptions({
    queryFn: () => getClient().getAnalytics(collectionName),
    queryKey: ["analytics", collectionName],
    refetchInterval: 30_000
  });
