'use client'

import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import {
  getSchema,
  updateSchema,
  queryDocuments,
  deleteNamespace,
  triggerCompaction,
  triggerWarm,
  type QueryRow,
} from '@/lib/api'
import {
  namespaceMetadataQueryOptions,
  schemaQueryOptions,
} from '@/lib/queries'
import { formatNumber, formatBytes, timeAgo } from '@/lib/utils'
import { StatusBadge } from '@/components/status-badge'

type Tab = 'documents' | 'schema' | 'settings'

const NamespaceDetailPage = () => {
  const params = useParams<{ namespace: string }>()
  const router = useRouter()
  const namespace = decodeURIComponent(params.namespace)
  const [activeTab, setActiveTab] = useState<Tab>('documents')

  const metaQuery = useQuery(namespaceMetadataQueryOptions(namespace))
  const meta = metaQuery.data ?? null

  const [actionMessage, setActionMessage] = useState<string | null>(null)

  const compactMutation = useMutation({
    mutationFn: () => triggerCompaction(namespace),
    onSuccess: (res) => setActionMessage(res.message || 'Compaction triggered'),
    onError: (err) => setActionMessage(err.message),
  })

  const warmMutation = useMutation({
    mutationFn: () => triggerWarm(namespace),
    onSuccess: (res) =>
      setActionMessage(res.message || 'Cache warming triggered'),
    onError: (err) => setActionMessage(err.message),
  })

  const tabs: readonly { readonly id: Tab; readonly label: string }[] = [
    { id: 'documents', label: 'Documents' },
    { id: 'schema', label: 'Schema' },
    { id: 'settings', label: 'Settings' },
  ]

  return (
    <div>
      {/* Back link + header */}
      <div className="mb-6">
        <Link
          href="/namespaces"
          className="mb-3 inline-flex items-center gap-1.5 text-xs text-text-muted transition-colors hover:text-text"
        >
          <ArrowLeftIcon className="size-3.5" />
          Back to namespaces
        </Link>

        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            <h1 className="font-mono text-xl font-semibold text-text">
              {namespace}
            </h1>
            {meta && <StatusBadge status={meta.index.status} />}
          </div>

          <div className="flex items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setActionMessage(null)
                compactMutation.mutate()
              }}
              disabled={compactMutation.isPending}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
            >
              {compactMutation.isPending ? 'Compacting...' : 'Compact'}
            </button>
            <button
              type="button"
              onClick={() => {
                setActionMessage(null)
                warmMutation.mutate()
              }}
              disabled={warmMutation.isPending}
              className="rounded-md px-3 py-1.5 text-xs font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
            >
              {warmMutation.isPending ? 'Warming...' : 'Warm Cache'}
            </button>
          </div>
        </div>

        {actionMessage && (
          <p className="mt-2 text-xs text-text-muted">{actionMessage}</p>
        )}
      </div>

      {/* Tabs */}
      <div className="mb-6 flex items-center gap-1 border-b border-border">
        {tabs.map((tab) => (
          <button
            type="button"
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={`relative px-4 py-2.5 text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? 'text-text'
                : 'text-text-muted hover:text-text'
            }`}
          >
            {tab.label}
            {activeTab === tab.id && (
              <span className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full bg-accent" />
            )}
          </button>
        ))}
      </div>

      {/* Meta loading / error */}
      {metaQuery.isLoading && (
        <div className="animate-pulse space-y-4">
          <div className="h-8 w-48 rounded bg-bg-hover" />
          <div className="h-40 rounded-lg bg-bg-hover" />
        </div>
      )}

      {metaQuery.error && !metaQuery.isLoading && (
        <div className="rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {metaQuery.error.message}
        </div>
      )}

      {/* Tab content */}
      {!metaQuery.isLoading && !metaQuery.error && (
        <>
          {activeTab === 'documents' && (
            <DocumentsTab namespace={namespace} />
          )}
          {activeTab === 'schema' && <SchemaTab namespace={namespace} />}
          {activeTab === 'settings' && (
            <SettingsTab
              namespace={namespace}
              meta={meta}
              onDeleted={() => router.push('/namespaces')}
            />
          )}
        </>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Documents Tab
// ---------------------------------------------------------------------------
const DocumentsTab = ({ namespace }: { readonly namespace: string }) => {
  const [query, setQuery] = useState('')
  const [rows, setRows] = useState<readonly QueryRow[]>([])
  const [nextCursor, setNextCursor] = useState<string | undefined>()
  const [isSearched, setIsSearched] = useState(false)

  const queryMutation = useMutation({
    mutationFn: (cursor?: string) => {
      const body: Record<string, unknown> = {
        top_k: 50,
        include_attributes: true,
      }
      if (query.trim()) {
        body.rank_by = { bm25: { query: query.trim(), fields: [] } }
      }
      if (cursor) {
        body.cursor = cursor
      }
      return queryDocuments(namespace, body)
    },
    onSuccess: (res, cursor) => {
      const newRows = res.rows ?? []
      if (cursor) {
        setRows((prev) => [...prev, ...newRows])
      } else {
        setRows(newRows)
      }
      setNextCursor(res.next_cursor)
      setIsSearched(true)
    },
  })

  const handleSearch = () => {
    setRows([])
    setNextCursor(undefined)
    queryMutation.mutate(undefined)
  }

  const handleListAll = () => {
    setQuery('')
    setRows([])
    setNextCursor(undefined)
    queryMutation.mutate(undefined)
  }

  const attributeColumns = getAttributeColumns(rows)
  const hasDist = rows.some((r) => r.$dist !== undefined)

  return (
    <div>
      {/* Query bar */}
      <div className="mb-4 flex items-center gap-3">
        <input
          type="text"
          placeholder="BM25 search query..."
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') handleSearch()
          }}
          className="flex-1 rounded-md border border-border bg-bg-input px-3 py-2 text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
        />
        <button
          type="button"
          onClick={handleSearch}
          disabled={queryMutation.isPending}
          className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          Search
        </button>
        <button
          type="button"
          onClick={handleListAll}
          disabled={queryMutation.isPending}
          className="rounded-md px-4 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
        >
          List All
        </button>
      </div>

      {queryMutation.error && (
        <div className="mb-4 rounded-lg border border-danger/30 bg-danger/5 px-4 py-3 text-sm text-danger">
          {queryMutation.error.message}
        </div>
      )}

      {/* Results */}
      {isSearched && (
        <>
          <div className="mb-3 flex items-center gap-2">
            <span className="inline-flex items-center rounded-full bg-bg-hover px-2.5 py-0.5 font-mono text-[11px] font-medium text-text-muted">
              {formatNumber(rows.length)} documents
            </span>
          </div>

          {rows.length === 0 && !queryMutation.isPending ? (
            <div className="flex flex-col items-center justify-center py-16">
              <p className="text-sm text-text-muted">No documents found</p>
            </div>
          ) : (
            <div className="overflow-x-auto rounded-lg border border-border">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-bg-card">
                    <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                      ID
                    </th>
                    {hasDist && (
                      <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                        dist
                      </th>
                    )}
                    {attributeColumns.map((col) => (
                      <th
                        key={col}
                        className="px-4 py-2.5 text-left text-xs font-medium text-text-muted"
                      >
                        {col}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {rows.map((row, i) => (
                    <tr
                      key={`${row.id}-${i}`}
                      className="border-b border-border transition-colors last:border-b-0 hover:bg-bg-hover/50"
                    >
                      <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-text">
                        {String(row.id)}
                      </td>
                      {hasDist && (
                        <td className="whitespace-nowrap px-4 py-2.5 font-mono text-xs text-text-muted">
                          {row.$dist !== undefined
                            ? row.$dist.toFixed(4)
                            : '-'}
                        </td>
                      )}
                      {attributeColumns.map((col) => (
                        <td
                          key={col}
                          className="max-w-48 truncate px-4 py-2.5 text-xs text-text-muted"
                          title={String(row[col] ?? '')}
                        >
                          {truncateValue(row[col])}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Load more */}
          {nextCursor && (
            <div className="mt-4 flex justify-center">
              <button
                type="button"
                onClick={() => queryMutation.mutate(nextCursor)}
                disabled={queryMutation.isPending}
                className="rounded-md px-4 py-2 text-sm font-medium text-text-muted transition-colors hover:bg-bg-hover hover:text-text disabled:opacity-50"
              >
                {queryMutation.isPending ? 'Loading...' : 'Load More'}
              </button>
            </div>
          )}
        </>
      )}

      {queryMutation.isPending && !isSearched && (
        <div className="flex justify-center py-12">
          <div className="size-5 animate-spin rounded-full border-2 border-border border-t-accent" />
        </div>
      )}
    </div>
  )
}

// ---------------------------------------------------------------------------
// Schema Tab
// ---------------------------------------------------------------------------
const SchemaTab = ({ namespace }: { readonly namespace: string }) => {
  const schemaQuery = useQuery(schemaQueryOptions(namespace))
  const [schemaText, setSchemaText] = useState('')
  const [isSynced, setIsSynced] = useState(false)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)
  const queryClient = useQueryClient()

  // Sync schemaText once on first load
  if (schemaQuery.data && !isSynced) {
    setSchemaText(JSON.stringify(schemaQuery.data, null, 2))
    setIsSynced(true)
  }

  const saveMutation = useMutation({
    mutationFn: (text: string) => {
      const parsed = JSON.parse(text)
      return updateSchema(namespace, parsed)
    },
    onSuccess: () => {
      setSaveMessage('Schema updated successfully')
      queryClient.invalidateQueries({ queryKey: ['schema', { namespace }] })
    },
    onError: (err) => {
      setSaveMessage(
        err instanceof SyntaxError
          ? `Invalid JSON: ${err.message}`
          : err.message
      )
    },
  })

  if (schemaQuery.isLoading) {
    return (
      <div className="animate-pulse space-y-4">
        <div className="h-6 w-32 rounded bg-bg-hover" />
        <div className="h-64 rounded-lg bg-bg-hover" />
      </div>
    )
  }

  const schema = schemaQuery.data
  const schemaEntries = schema
    ? Object.entries(schema).map(([name, def]) => {
        const d = def as Record<string, unknown> | undefined
        return {
          name,
          type: String(d?.type ?? 'unknown'),
          filterable: Boolean(d?.filterable),
          hasFullTextSearch:
            d?.full_text_search !== undefined && d?.full_text_search !== false,
        }
      })
    : []

  return (
    <div className="space-y-6">
      {/* Schema table */}
      {schemaEntries.length > 0 && (
        <div>
          <h3 className="mb-3 text-sm font-medium text-text">
            Schema Definition
          </h3>
          <div className="overflow-x-auto rounded-lg border border-border">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border bg-bg-card">
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Attribute Name
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Type
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    Filterable
                  </th>
                  <th className="px-4 py-2.5 text-left text-xs font-medium text-text-muted">
                    FTS
                  </th>
                </tr>
              </thead>
              <tbody>
                {schemaEntries.map((entry) => (
                  <tr
                    key={entry.name}
                    className="border-b border-border last:border-b-0"
                  >
                    <td className="px-4 py-2.5 font-mono text-xs text-text">
                      {entry.name}
                    </td>
                    <td className="px-4 py-2.5 font-mono text-xs text-text-muted">
                      {entry.type}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {entry.filterable ? (
                        <span className="text-success">Yes</span>
                      ) : (
                        <span className="text-text-dim">No</span>
                      )}
                    </td>
                    <td className="px-4 py-2.5 text-xs">
                      {entry.hasFullTextSearch ? (
                        <span className="text-success">Yes</span>
                      ) : (
                        <span className="text-text-dim">No</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* JSON editor */}
      <div>
        <h3 className="mb-3 text-sm font-medium text-text">Edit Schema</h3>
        <textarea
          value={schemaText}
          onChange={(e) => {
            setSchemaText(e.target.value)
            setSaveMessage(null)
          }}
          rows={16}
          spellCheck={false}
          className="w-full resize-y rounded-lg border border-border bg-bg-input px-4 py-3 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
        />

        {saveMutation.error && (
          <p className="mt-2 text-xs text-danger">{saveMutation.error.message}</p>
        )}
        {saveMessage && (
          <p className="mt-2 text-xs text-success">{saveMessage}</p>
        )}

        <div className="mt-3 flex justify-end">
          <button
            type="button"
            onClick={() => saveMutation.mutate(schemaText)}
            disabled={saveMutation.isPending}
            className="rounded-md bg-accent px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-accent-hover disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving...' : 'Save Schema'}
          </button>
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Settings Tab
// ---------------------------------------------------------------------------
interface SettingsTabProps {
  readonly namespace: string
  readonly meta: {
    readonly approx_row_count: number
    readonly approx_logical_bytes: number
    readonly created_at: string
    readonly updated_at: string
    readonly index: { readonly status: string; readonly unindexed_bytes?: number }
  } | null
  readonly onDeleted: () => void
}

const SettingsTab = ({ namespace, meta, onDeleted }: SettingsTabProps) => {
  const [confirmText, setConfirmText] = useState('')

  const deleteMutation = useMutation({
    mutationFn: () => deleteNamespace(namespace),
    onSuccess: () => onDeleted(),
  })

  return (
    <div className="space-y-8">
      {/* Metadata */}
      {meta && (
        <div>
          <h3 className="mb-4 text-sm font-medium text-text">
            Namespace Metadata
          </h3>
          <div className="divide-y divide-border rounded-lg border border-border bg-bg-card">
            <MetaRow
              label="Created"
              value={meta.created_at ? timeAgo(meta.created_at) : '-'}
              sub={meta.created_at}
            />
            <MetaRow
              label="Updated"
              value={meta.updated_at ? timeAgo(meta.updated_at) : '-'}
              sub={meta.updated_at}
            />
            <MetaRow
              label="Approx. Row Count"
              value={formatNumber(meta.approx_row_count)}
              isMono
            />
            <MetaRow
              label="Approx. Logical Size"
              value={formatBytes(meta.approx_logical_bytes)}
              isMono
            />
            <MetaRow label="Index Status" value={meta.index.status}>
              <StatusBadge status={meta.index.status} />
            </MetaRow>
            {meta.index.unindexed_bytes !== undefined && (
              <MetaRow
                label="Unindexed Bytes"
                value={formatBytes(meta.index.unindexed_bytes)}
                isMono
              />
            )}
          </div>
        </div>
      )}

      {/* Danger zone */}
      <div>
        <h3 className="mb-4 text-sm font-medium text-danger">Danger Zone</h3>
        <div className="rounded-lg border border-danger/30 bg-danger/5 p-5">
          <p className="mb-1 text-sm text-text">Delete this namespace</p>
          <p className="mb-4 text-xs text-text-muted">
            This action cannot be undone. All documents, vectors, and schema
            data will be permanently deleted.
          </p>

          <div className="flex items-end gap-3">
            <div className="flex-1">
              <label className="mb-1.5 block text-xs text-text-muted">
                Type <span className="font-mono text-text">{namespace}</span> to
                confirm
              </label>
              <input
                type="text"
                value={confirmText}
                onChange={(e) => setConfirmText(e.target.value)}
                placeholder={namespace}
                className="w-full rounded-md border border-border bg-bg-input px-3 py-2 font-mono text-sm text-text placeholder:text-text-dim focus:border-border-hover focus:outline-none"
              />
            </div>
            <button
              type="button"
              onClick={() => deleteMutation.mutate()}
              disabled={confirmText !== namespace || deleteMutation.isPending}
              className="whitespace-nowrap rounded-md bg-danger/10 px-4 py-2 text-sm font-medium text-danger transition-colors hover:bg-danger/20 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {deleteMutation.isPending ? 'Deleting...' : 'Delete Namespace'}
            </button>
          </div>

          {deleteMutation.error && (
            <p className="mt-3 text-xs text-danger">
              {deleteMutation.error.message}
            </p>
          )}
        </div>
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Shared Components
// ---------------------------------------------------------------------------
interface MetaRowProps {
  readonly label: string
  readonly value: string
  readonly sub?: string
  readonly isMono?: boolean
  readonly children?: React.ReactNode
}

const MetaRow = ({ label, value, sub, isMono, children }: MetaRowProps) => {
  return (
    <div className="flex items-center justify-between px-4 py-3">
      <span className="text-sm text-text-muted">{label}</span>
      <div className="flex items-center gap-2">
        {children ?? (
          <span
            className={`text-sm text-text ${isMono ? 'font-mono' : ''}`}
            title={sub}
          >
            {value}
          </span>
        )}
      </div>
    </div>
  )
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------
const ArrowLeftIcon = ({ className }: { readonly className?: string }) => {
  return (
    <svg
      className={className}
      viewBox="0 0 16 16"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M10 3L5 8l5 5" />
    </svg>
  )
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------
function getAttributeColumns(rows: readonly QueryRow[]): readonly string[] {
  const ignored = new Set(['id', '$dist'])
  const counts = new Map<string, number>()

  for (const row of rows.slice(0, 20)) {
    for (const key of Object.keys(row)) {
      if (!ignored.has(key)) {
        counts.set(key, (counts.get(key) ?? 0) + 1)
      }
    }
  }

  return [...counts.entries()]
    .sort((a, b) => b[1] - a[1])
    .slice(0, 4)
    .map(([key]) => key)
}

function truncateValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  if (typeof value === 'string') {
    return value.length > 80 ? `${value.slice(0, 80)}...` : value
  }
  if (typeof value === 'number' || typeof value === 'boolean') {
    return String(value)
  }
  if (Array.isArray(value)) {
    return `[${value.length} items]`
  }
  if (typeof value === 'object') {
    const str = JSON.stringify(value)
    return str.length > 80 ? `${str.slice(0, 80)}...` : str
  }
  return String(value)
}

export default NamespaceDetailPage
