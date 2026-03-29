import { queryOptions } from '@tanstack/react-query'
import {
  getHealth,
  listNamespaces,
  getNamespaceMetadata,
  getSchema,
  queryDocuments,
  getAdminConfig,
  getMetrics,
  type QueryRequest,
} from '@/lib/api'

export const healthQueryOptions = () =>
  queryOptions({
    queryKey: ['health'],
    queryFn: () => getHealth(),
  })

export const namespacesQueryOptions = (params?: {
  readonly prefix?: string
  readonly cursor?: string
  readonly pageSize?: number
}) =>
  queryOptions({
    queryKey: ['namespaces', params],
    queryFn: () =>
      listNamespaces(params?.prefix, params?.cursor, params?.pageSize ?? 100),
  })

export const namespaceMetadataQueryOptions = (namespace: string) =>
  queryOptions({
    queryKey: ['namespace-metadata', { namespace }],
    queryFn: () => getNamespaceMetadata(namespace),
  })

export const schemaQueryOptions = (namespace: string) =>
  queryOptions({
    queryKey: ['schema', { namespace }],
    queryFn: () => getSchema(namespace),
  })

export const queryDocumentsOptions = (
  namespace: string,
  body: QueryRequest
) =>
  queryOptions({
    queryKey: ['query', { namespace, body }],
    queryFn: () => queryDocuments(namespace, body),
    enabled: false,
  })

export const adminConfigQueryOptions = () =>
  queryOptions({
    queryKey: ['admin-config'],
    queryFn: () => getAdminConfig(),
  })

export const metricsQueryOptions = () =>
  queryOptions({
    queryKey: ['metrics'],
    queryFn: () => getMetrics(),
    refetchInterval: 10_000,
  })
