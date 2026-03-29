import { queryOptions } from "@tanstack/react-query";
import {
  getAdminConfig,
  getHealth,
  getMetrics,
  getNamespaceMetadata,
  getSchema,
  listNamespaces
} from "@/lib/api";

export const healthQueryOptions = () =>
  queryOptions({
    queryFn: () => getHealth(),
    queryKey: ["health"]
  });

export const namespacesQueryOptions = (params?: {
  readonly prefix?: string;
  readonly cursor?: string;
  readonly pageSize?: number;
}) =>
  queryOptions({
    queryFn: () =>
      listNamespaces(params?.prefix, params?.cursor, params?.pageSize ?? 100),
    queryKey: ["namespaces", params]
  });

export const namespaceMetadataQueryOptions = (namespace: string) =>
  queryOptions({
    queryFn: () => getNamespaceMetadata(namespace),
    queryKey: ["namespace-metadata", { namespace }]
  });

export const schemaQueryOptions = (namespace: string) =>
  queryOptions({
    queryFn: () => getSchema(namespace),
    queryKey: ["schema", { namespace }]
  });

export const adminConfigQueryOptions = () =>
  queryOptions({
    queryFn: () => getAdminConfig(),
    queryKey: ["admin-config"]
  });

export const metricsQueryOptions = () =>
  queryOptions({
    queryFn: () => getMetrics(),
    queryKey: ["metrics"],
    refetchInterval: 10_000
  });
