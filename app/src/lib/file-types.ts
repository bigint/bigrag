/**
 * File-type categories accepted by bigRAG's Docling ingester.
 * Stored per-collection in `collection.metadata.allowed_file_types` — when
 * empty or missing, all types are allowed. When non-empty, the Studio refuses
 * uploads whose extension isn't in the list.
 */

export const FILE_TYPE_CATEGORIES: Record<string, string[]> = {
  Documents: ["pdf", "docx", "pptx", "xlsx"],
  Text: ["md", "txt", "html", "htm", "csv", "tsv", "xml", "json"],
  Images: ["png", "jpg", "jpeg", "tiff", "bmp", "gif"],
};

export const ALL_FILE_TYPES = Object.values(FILE_TYPE_CATEGORIES).flat();

export const extensionOf = (filename: string): string => {
  const dot = filename.lastIndexOf(".");
  if (dot < 0) return "";
  return filename.slice(dot + 1).toLowerCase();
};

export const getAllowedFileTypes = (
  metadata: Record<string, unknown> | null | undefined,
): string[] => {
  const raw = metadata?.allowed_file_types;
  if (!Array.isArray(raw)) return [];
  return raw.filter((v): v is string => typeof v === "string").map((v) => v.toLowerCase());
};

export const filterBlockedFiles = (
  files: File[],
  allowed: string[],
): { accepted: File[]; rejected: File[] } => {
  if (allowed.length === 0) return { accepted: files, rejected: [] };
  const accepted: File[] = [];
  const rejected: File[] = [];
  for (const file of files) {
    if (allowed.includes(extensionOf(file.name))) accepted.push(file);
    else rejected.push(file);
  }
  return { accepted, rejected };
};

export const acceptAttribute = (allowed: string[]): string => {
  const list = allowed.length ? allowed : ALL_FILE_TYPES;
  return list.map((t) => `.${t}`).join(",");
};
