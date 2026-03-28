"use client";

import { useState, useEffect, useRef, useCallback } from "react";
import {
  writeDocuments,
  queryDocuments,
  deleteNamespace,
  getNamespaceMetadata,
  type QueryRow,
  type WriteRequest,
} from "@/lib/api";
import { formatBytes, formatNumber } from "@/lib/utils";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface UploadedFile {
  name: string;
  size: number;
  pages: number;
  chunks: number;
  uploadedAt: Date;
}

// ---------------------------------------------------------------------------
// PDF helpers (dynamic import to avoid SSR)
// ---------------------------------------------------------------------------

async function loadPdfJs() {
  const pdfjs = await import("pdfjs-dist");
  pdfjs.GlobalWorkerOptions.workerSrc =
    "https://unpkg.com/pdfjs-dist@5.5.207/build/pdf.worker.min.mjs";
  return pdfjs;
}

async function extractTextFromPdf(
  file: File
): Promise<{ pages: { pageNum: number; text: string }[] }> {
  const pdfjs = await loadPdfJs();
  const arrayBuffer = await file.arrayBuffer();
  const pdf = await pdfjs.getDocument({ data: arrayBuffer }).promise;
  const pages: { pageNum: number; text: string }[] = [];
  for (let i = 1; i <= pdf.numPages; i++) {
    const page = await pdf.getPage(i);
    const content = await page.getTextContent();
    const text = (content.items as { str: string }[])
      .map((item) => item.str)
      .join(" ");
    pages.push({ pageNum: i, text });
  }
  return { pages };
}

// ---------------------------------------------------------------------------
// Text chunking
// ---------------------------------------------------------------------------

function chunkText(
  text: string,
  chunkSize = 500,
  overlap = 50
): string[] {
  const words = text.split(/\s+/).filter(Boolean);
  if (words.length === 0) return [];
  const chunks: string[] = [];
  let start = 0;
  while (start < words.length) {
    const end = Math.min(start + chunkSize, words.length);
    chunks.push(words.slice(start, end).join(" "));
    start += chunkSize - overlap;
  }
  return chunks;
}

// ---------------------------------------------------------------------------
// bigRAG helpers
// ---------------------------------------------------------------------------

async function storeChunks(
  namespace: string,
  filename: string,
  chunks: { text: string; page: number; chunkIdx: number }[]
) {
  const rows = chunks.map((chunk) => ({
    id: `${filename}__p${chunk.page}_c${chunk.chunkIdx}`,
    filename,
    page_number: chunk.page,
    chunk_index: chunk.chunkIdx,
    content: chunk.text,
    char_count: chunk.text.length,
  }));

  await writeDocuments(namespace, {
    upsert_rows: rows,
    distance_metric: "cosine_distance",
    schema: {
      content: { type: "string", full_text_search: true, filterable: false },
      filename: { type: "string", filterable: true },
      page_number: { type: "uint", filterable: true },
      chunk_index: { type: "uint", filterable: true },
      char_count: { type: "uint", filterable: true },
    },
  } as WriteRequest);
}

async function searchVault(namespace: string, query: string) {
  return queryDocuments(namespace, {
    rank_by: ["content", "BM25", query],
    top_k: 20,
    include_attributes: true,
  });
}

async function deleteDocumentChunks(namespace: string, filename: string) {
  await writeDocuments(namespace, {
    delete_by_filter: {
      filter: ["filename", "Eq", filename],
    },
  });
}

// ---------------------------------------------------------------------------
// Icons
// ---------------------------------------------------------------------------

function UploadIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
      <polyline points="17 8 12 3 7 8" />
      <line x1="12" y1="3" x2="12" y2="15" />
    </svg>
  );
}

function FileIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14 2 14 8 20 8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
      <polyline points="10 9 9 9 8 9" />
    </svg>
  );
}

function SearchIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="11" cy="11" r="8" />
      <line x1="21" y1="21" x2="16.65" y2="16.65" />
    </svg>
  );
}

function ChevronIcon({ className, open }: { className?: string; open: boolean }) {
  return (
    <svg
      className={`${className ?? ""} transition-transform ${open ? "rotate-180" : ""}`}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="6 9 12 15 18 9" />
    </svg>
  );
}

function XIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function SettingsIcon({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  );
}

function SpinnerIcon({ className }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className ?? ""}`}
      viewBox="0 0 24 24"
      fill="none"
    >
      <circle
        cx="12"
        cy="12"
        r="10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
        className="opacity-20"
      />
      <path
        d="M12 2a10 10 0 0 1 10 10"
        stroke="currentColor"
        strokeWidth="3"
        strokeLinecap="round"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

const MAX_FILE_SIZE = 50 * 1024 * 1024; // 50 MB
const DEFAULT_NAMESPACE = "vault_documents";

export default function VaultPage() {
  // Settings
  const [chunkSize, setChunkSize] = useState(500);
  const [chunkOverlap, setChunkOverlap] = useState(50);
  const [namespace, setNamespace] = useState(DEFAULT_NAMESPACE);
  const [showSettings, setShowSettings] = useState(false);

  // Upload
  const [files, setFiles] = useState<UploadedFile[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadProgress, setUploadProgress] = useState("");
  const [isDragOver, setIsDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Search
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<QueryRow[]>([]);
  const [isSearching, setIsSearching] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);

  // General
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [namespaceStats, setNamespaceStats] = useState<{
    rows: number;
    bytes: number;
  } | null>(null);

  // -------------------------------------------------------------------------
  // Load existing documents on mount
  // -------------------------------------------------------------------------

  const loadExistingDocuments = useCallback(async () => {
    try {
      const metadata = await getNamespaceMetadata(namespace);
      setNamespaceStats({
        rows: metadata.approx_row_count,
        bytes: metadata.approx_logical_bytes,
      });

      // Fetch a sample to discover unique filenames
      const result = await queryDocuments(namespace, {
        top_k: 1000,
        include_attributes: ["filename", "page_number", "chunk_index"],
      });

      if (result.rows && result.rows.length > 0) {
        const fileMap = new Map<
          string,
          { pages: Set<number>; chunks: number }
        >();
        for (const row of result.rows) {
          const fname = row.filename as string;
          if (!fname) continue;
          if (!fileMap.has(fname)) {
            fileMap.set(fname, { pages: new Set(), chunks: 0 });
          }
          const entry = fileMap.get(fname)!;
          entry.pages.add(row.page_number as number);
          entry.chunks += 1;
        }

        const existing: UploadedFile[] = [];
        fileMap.forEach((val, name) => {
          existing.push({
            name,
            size: 0,
            pages: val.pages.size,
            chunks: val.chunks,
            uploadedAt: new Date(),
          });
        });
        setFiles(existing);
      }
    } catch {
      // Namespace may not exist yet, that's fine
    } finally {
      setLoading(false);
    }
  }, [namespace]);

  useEffect(() => {
    setLoading(true);
    loadExistingDocuments();
  }, [loadExistingDocuments]);

  // -------------------------------------------------------------------------
  // Drag and drop handlers
  // -------------------------------------------------------------------------

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  const processFile = useCallback(
    async (file: File) => {
      if (file.type !== "application/pdf") {
        setError("Only PDF files are supported.");
        return;
      }

      if (file.size > MAX_FILE_SIZE) {
        setError("File exceeds 50MB limit.");
        return;
      }

      setError(null);
      setIsUploading(true);

      try {
        // Step 1: Extract text
        setUploadProgress(`Extracting text from ${file.name}...`);
        const { pages } = await extractTextFromPdf(file);

        // Step 2: Chunk
        setUploadProgress(
          `Chunking ${pages.length} pages from ${file.name}...`
        );
        const allChunks: { text: string; page: number; chunkIdx: number }[] =
          [];
        let globalChunkIdx = 0;

        for (const page of pages) {
          if (!page.text.trim()) continue;
          const pageChunks = chunkText(page.text, chunkSize, chunkOverlap);
          for (const text of pageChunks) {
            allChunks.push({
              text,
              page: page.pageNum,
              chunkIdx: globalChunkIdx++,
            });
          }
        }

        if (allChunks.length === 0) {
          setError(
            `No extractable text found in ${file.name}. The PDF may be image-based.`
          );
          setIsUploading(false);
          setUploadProgress("");
          return;
        }

        // Step 3: Store in bigRAG (batch in groups of 100)
        setUploadProgress(
          `Uploading ${allChunks.length} chunks to bigRAG...`
        );
        const batchSize = 100;
        for (let i = 0; i < allChunks.length; i += batchSize) {
          const batch = allChunks.slice(i, i + batchSize);
          setUploadProgress(
            `Uploading chunks ${i + 1}-${Math.min(i + batchSize, allChunks.length)} of ${allChunks.length}...`
          );
          await storeChunks(namespace, file.name, batch);
        }

        // Step 4: Update local state
        const newFile: UploadedFile = {
          name: file.name,
          size: file.size,
          pages: pages.length,
          chunks: allChunks.length,
          uploadedAt: new Date(),
        };

        setFiles((prev) => {
          const existing = prev.filter((f) => f.name !== file.name);
          return [...existing, newFile];
        });

        setUploadProgress(`${file.name} uploaded successfully.`);
        setTimeout(() => setUploadProgress(""), 3000);

        // Refresh stats
        loadExistingDocuments();
      } catch (err) {
        setError(
          err instanceof Error
            ? `Failed to process ${file.name}: ${err.message}`
            : "Upload failed."
        );
      } finally {
        setIsUploading(false);
      }
    },
    [namespace, chunkSize, chunkOverlap, loadExistingDocuments]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      const droppedFiles = Array.from(e.dataTransfer.files);
      for (const file of droppedFiles) {
        processFile(file);
      }
    },
    [processFile]
  );

  const handleFileInput = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const selectedFiles = e.target.files;
      if (!selectedFiles) return;
      for (const file of Array.from(selectedFiles)) {
        processFile(file);
      }
      // Reset so the same file can be selected again
      e.target.value = "";
    },
    [processFile]
  );

  // -------------------------------------------------------------------------
  // Search
  // -------------------------------------------------------------------------

  const handleSearch = useCallback(async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true);
    setError(null);
    setHasSearched(true);

    try {
      const result = await searchVault(namespace, searchQuery.trim());
      setSearchResults(result.rows ?? []);
    } catch (err) {
      setError(
        err instanceof Error ? `Search failed: ${err.message}` : "Search failed."
      );
      setSearchResults([]);
    } finally {
      setIsSearching(false);
    }
  }, [namespace, searchQuery]);

  // -------------------------------------------------------------------------
  // Delete handlers
  // -------------------------------------------------------------------------

  const handleDeleteFile = useCallback(
    async (filename: string) => {
      setError(null);
      try {
        await deleteDocumentChunks(namespace, filename);
        setFiles((prev) => prev.filter((f) => f.name !== filename));
        // Clear search results that belong to deleted file
        setSearchResults((prev) =>
          prev.filter((r) => r.filename !== filename)
        );
        loadExistingDocuments();
      } catch (err) {
        setError(
          err instanceof Error
            ? `Delete failed: ${err.message}`
            : "Delete failed."
        );
      }
    },
    [namespace, loadExistingDocuments]
  );

  const handleClearAll = useCallback(async () => {
    if (!confirm("Delete all documents in the vault? This cannot be undone."))
      return;
    setError(null);
    try {
      await deleteNamespace(namespace);
      setFiles([]);
      setSearchResults([]);
      setNamespaceStats(null);
      setHasSearched(false);
    } catch (err) {
      setError(
        err instanceof Error
          ? `Clear failed: ${err.message}`
          : "Clear all failed."
      );
    }
  }, [namespace]);

  // -------------------------------------------------------------------------
  // Highlight matching terms in text
  // -------------------------------------------------------------------------

  function highlightText(text: string, query: string) {
    if (!query.trim()) return text;
    const terms = query
      .trim()
      .split(/\s+/)
      .filter(Boolean)
      .map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"));
    if (terms.length === 0) return text;
    const regex = new RegExp(`(${terms.join("|")})`, "gi");
    const parts = text.split(regex);
    return parts.map((part, i) =>
      regex.test(part) ? (
        <mark
          key={i}
          className="bg-blue-500/20 text-blue-400 rounded-sm px-0.5"
        >
          {part}
        </mark>
      ) : (
        part
      )
    );
  }

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-[#09090b] text-[#fafafa]">
      <div className="mx-auto max-w-6xl px-6 py-10">
        {/* Page header */}
        <div className="mb-8 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight">Vault</h1>
            <p className="mt-1 text-[13px] text-[#a1a1aa]">
              Upload PDFs, extract text, and search across all documents
              {namespaceStats && (
                <span className="ml-2 text-[#71717a]">
                  &middot; {formatNumber(namespaceStats.rows)} chunks &middot;{" "}
                  {formatBytes(namespaceStats.bytes)}
                </span>
              )}
            </p>
          </div>
          <button
            onClick={() => setShowSettings((s) => !s)}
            className="flex items-center gap-1.5 rounded-md border border-[#27272a] bg-[#18181b] px-3 py-2 text-sm text-[#a1a1aa] transition-colors hover:border-[#3f3f46] hover:text-[#fafafa]"
          >
            <SettingsIcon className="size-4" />
            Settings
          </button>
        </div>

        {/* Settings panel */}
        {showSettings && (
          <div className="mb-6 rounded-lg border border-[#27272a] bg-[#18181b] p-5">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-sm font-medium text-[#fafafa]">
                Processing Settings
              </h2>
              <button
                onClick={() => setShowSettings(false)}
                className="text-[#71717a] transition-colors hover:text-[#a1a1aa]"
              >
                <XIcon className="size-4" />
              </button>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
              <div>
                <label className="mb-1.5 block text-[13px] text-[#a1a1aa]">
                  Chunk size (words)
                </label>
                <input
                  type="number"
                  min={50}
                  max={5000}
                  value={chunkSize}
                  onChange={(e) =>
                    setChunkSize(Math.max(50, parseInt(e.target.value) || 500))
                  }
                  className="w-full rounded-md border border-[#27272a] bg-[#09090b] px-3 py-2 text-sm font-mono text-[#fafafa] focus:border-[#3f3f46] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[13px] text-[#a1a1aa]">
                  Chunk overlap (words)
                </label>
                <input
                  type="number"
                  min={0}
                  max={500}
                  value={chunkOverlap}
                  onChange={(e) =>
                    setChunkOverlap(
                      Math.max(0, parseInt(e.target.value) || 50)
                    )
                  }
                  className="w-full rounded-md border border-[#27272a] bg-[#09090b] px-3 py-2 text-sm font-mono text-[#fafafa] focus:border-[#3f3f46] focus:outline-none"
                />
              </div>
              <div>
                <label className="mb-1.5 block text-[13px] text-[#a1a1aa]">
                  Vault namespace
                </label>
                <input
                  type="text"
                  value={namespace}
                  onChange={(e) => setNamespace(e.target.value || DEFAULT_NAMESPACE)}
                  className="w-full rounded-md border border-[#27272a] bg-[#09090b] px-3 py-2 text-sm font-mono text-[#fafafa] focus:border-[#3f3f46] focus:outline-none"
                />
              </div>
            </div>
          </div>
        )}

        {/* Error banner */}
        {error && (
          <div className="mb-6 flex items-center justify-between rounded-lg border border-red-500/20 bg-red-500/10 px-4 py-3 text-sm text-red-500">
            <span>{error}</span>
            <button
              onClick={() => setError(null)}
              className="ml-4 text-red-500/60 transition-colors hover:text-red-500"
            >
              <XIcon className="size-4" />
            </button>
          </div>
        )}

        {/* Upload drop zone */}
        <div
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          onDrop={handleDrop}
          onClick={() => !isUploading && fileInputRef.current?.click()}
          className={`mb-8 flex cursor-pointer flex-col items-center justify-center rounded-lg border-2 border-dashed px-6 py-12 transition-colors ${
            isDragOver
              ? "border-blue-500 bg-blue-500/5"
              : "border-[#27272a] bg-[#18181b] hover:border-[#3f3f46]"
          } ${isUploading ? "pointer-events-none opacity-60" : ""}`}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,application/pdf"
            multiple
            onChange={handleFileInput}
            className="hidden"
          />

          {isUploading ? (
            <>
              <SpinnerIcon className="mb-3 size-8 text-blue-500" />
              <p className="text-sm text-[#fafafa]">{uploadProgress}</p>
            </>
          ) : (
            <>
              <UploadIcon
                className={`mb-3 size-8 ${isDragOver ? "text-blue-500" : "text-[#71717a]"}`}
              />
              <p className="text-sm text-[#fafafa]">
                Drop PDFs here or click to browse
              </p>
              <p className="mt-1 text-[13px] text-[#71717a]">
                Supports: PDF (max 50MB)
              </p>
            </>
          )}
        </div>

        {/* Search */}
        <div className="mb-8">
          <label className="mb-2 block text-sm font-medium text-[#fafafa]">
            Search across all documents
          </label>
          <div className="flex gap-2">
            <div className="relative flex-1">
              <SearchIcon className="absolute left-3 top-1/2 size-4 -translate-y-1/2 text-[#71717a]" />
              <input
                type="text"
                placeholder="Search query..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && handleSearch()}
                className="w-full rounded-md border border-[#27272a] bg-[#18181b] py-2 pl-10 pr-3 text-sm text-[#fafafa] placeholder-[#71717a] focus:border-[#3f3f46] focus:outline-none"
              />
            </div>
            <button
              onClick={handleSearch}
              disabled={isSearching || !searchQuery.trim()}
              className="flex items-center gap-2 rounded-md bg-blue-500 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isSearching ? (
                <SpinnerIcon className="size-4" />
              ) : (
                <SearchIcon className="size-4" />
              )}
              Search
            </button>
          </div>
        </div>

        {/* Search results */}
        {hasSearched && (
          <div className="mb-8">
            <h2 className="mb-3 text-sm font-medium text-[#fafafa]">
              Results
              {searchResults.length > 0 && (
                <span className="ml-2 text-[#71717a]">
                  ({searchResults.length})
                </span>
              )}
            </h2>

            {searchResults.length === 0 ? (
              <div className="rounded-lg border border-[#27272a] bg-[#18181b] px-5 py-12 text-center text-sm text-[#71717a]">
                No results found. Try a different query.
              </div>
            ) : (
              <div className="space-y-2">
                {searchResults.map((row, i) => (
                  <div
                    key={`${row.id}-${i}`}
                    className="rounded-lg border border-[#27272a] bg-[#18181b] px-5 py-4 transition-colors hover:border-[#3f3f46]"
                  >
                    <div className="mb-2 flex items-center justify-between">
                      <div className="flex items-center gap-2 text-sm">
                        <FileIcon className="size-4 text-blue-500" />
                        <span className="font-medium text-[#fafafa]">
                          {row.filename as string}
                        </span>
                        <span className="text-[#71717a]">&middot;</span>
                        <span className="font-mono text-[13px] text-[#a1a1aa]">
                          Page {row.page_number as number}
                        </span>
                        <span className="text-[#71717a]">&middot;</span>
                        <span className="font-mono text-[13px] text-[#a1a1aa]">
                          Chunk {row.chunk_index as number}
                        </span>
                      </div>
                      {row.$dist !== undefined && (
                        <span className="rounded-full bg-blue-500/10 px-2.5 py-0.5 font-mono text-xs text-blue-400">
                          score: {(row.$dist as number).toFixed(2)}
                        </span>
                      )}
                    </div>
                    <p className="line-clamp-3 text-[13px] leading-relaxed text-[#a1a1aa]">
                      &ldquo;
                      {highlightText(
                        truncateText(row.content as string, 300),
                        searchQuery
                      )}
                      &rdquo;
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* Uploaded documents */}
        <div className="rounded-lg border border-[#27272a] bg-[#18181b]">
          <div className="flex items-center justify-between border-b border-[#27272a] px-5 py-4">
            <h2 className="text-sm font-medium text-[#fafafa]">
              Uploaded Documents
              {files.length > 0 && (
                <span className="ml-2 text-[#71717a]">({files.length})</span>
              )}
            </h2>
            {files.length > 0 && (
              <button
                onClick={handleClearAll}
                className="rounded-md px-3 py-1.5 text-[13px] text-red-500 transition-colors hover:bg-red-500/10"
              >
                Clear All
              </button>
            )}
          </div>

          {loading ? (
            <div className="divide-y divide-[#27272a]">
              {Array.from({ length: 3 }).map((_, i) => (
                <div key={i} className="flex items-center gap-4 px-5 py-3.5">
                  <div className="h-4 w-4 animate-pulse rounded bg-[#27272a]" />
                  <div className="h-4 w-32 animate-pulse rounded bg-[#27272a]" />
                  <div className="ml-auto h-4 w-16 animate-pulse rounded bg-[#27272a]" />
                  <div className="h-4 w-16 animate-pulse rounded bg-[#27272a]" />
                  <div className="h-4 w-16 animate-pulse rounded bg-[#27272a]" />
                </div>
              ))}
            </div>
          ) : files.length === 0 ? (
            <div className="px-5 py-12 text-center text-sm text-[#71717a]">
              No documents uploaded yet. Drop a PDF above to get started.
            </div>
          ) : (
            <div className="divide-y divide-[#27272a]">
              {files.map((file) => (
                <div
                  key={file.name}
                  className="group flex items-center gap-4 px-5 py-3.5 transition-colors hover:bg-[#27272a]/30"
                >
                  <FileIcon className="size-4 shrink-0 text-[#71717a]" />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium text-[#fafafa]">
                    {file.name}
                  </span>
                  <span className="shrink-0 text-[13px] text-[#a1a1aa]">
                    {file.pages} {file.pages === 1 ? "page" : "pages"}
                  </span>
                  <span className="shrink-0 font-mono text-[13px] text-[#a1a1aa]">
                    {formatNumber(file.chunks)} chunks
                  </span>
                  {file.size > 0 && (
                    <span className="shrink-0 font-mono text-[13px] text-[#71717a]">
                      {formatBytes(file.size)}
                    </span>
                  )}
                  <button
                    onClick={(e) => {
                      e.stopPropagation();
                      handleDeleteFile(file.name);
                    }}
                    className="shrink-0 rounded p-1 text-[#71717a] opacity-0 transition-all hover:bg-red-500/10 hover:text-red-500 group-hover:opacity-100"
                    title={`Delete ${file.name}`}
                  >
                    <XIcon className="size-4" />
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Helper
// ---------------------------------------------------------------------------

function truncateText(text: string, maxLength: number): string {
  if (text.length <= maxLength) return text;
  return text.slice(0, maxLength) + "...";
}
