import type { FileInput } from "./types/documents.js";

export async function normalizeFileInput(file: FileInput): Promise<{ blob: Blob; name: string }> {
  if (file instanceof Blob) {
    const name = file instanceof File ? file.name : "document";
    return { blob: file, name };
  }

  if (file instanceof Uint8Array || (typeof Buffer !== "undefined" && Buffer.isBuffer(file))) {
    return { blob: new Blob([file as BlobPart]), name: "document" };
  }

  if (typeof file === "object" && "path" in file) {
    const { createReadStream, statSync } = await import("node:fs");
    const { basename } = await import("node:path");
    const { Readable } = await import("node:stream");
    const name = file.name ?? basename(file.path);
    const size = statSync(file.path).size;
    const nodeStream = createReadStream(file.path);
    const webStream = (
      Readable as unknown as { toWeb: (s: NodeJS.ReadableStream) => ReadableStream }
    ).toWeb(nodeStream);
    const blob = await new Response(webStream, {
      headers: { "Content-Length": String(size) },
    }).blob();
    return { blob, name };
  }

  throw new Error("Unsupported file input type");
}
