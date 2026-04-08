import type { FileInput } from "./types/documents.js";

/**
 * Normalize a single {@link FileInput} into a `Blob` suitable for `FormData`
 * along with a human-readable file name.
 *
 * This consolidates the duplicated detection logic that was previously
 * inlined in both `_buildUploadForm` and `batchUploadDocuments`.
 */
export async function normalizeFileInput(file: FileInput): Promise<{ blob: Blob; name: string }> {
  if (file instanceof Blob) {
    const name = file instanceof File ? file.name : "document";
    return { blob: file, name };
  }

  if (file instanceof Uint8Array || (typeof Buffer !== "undefined" && Buffer.isBuffer(file))) {
    return { blob: new Blob([file as BlobPart]), name: "document" };
  }

  if (typeof file === "object" && "path" in file) {
    const { readFile } = await import("node:fs/promises");
    const { basename } = await import("node:path");
    const data = await readFile(file.path);
    const name = file.name ?? basename(file.path);
    return { blob: new Blob([data]), name };
  }

  // Exhaustiveness -- should never be reached.
  throw new Error("Unsupported file input type");
}
