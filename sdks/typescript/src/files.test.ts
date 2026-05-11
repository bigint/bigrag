import { mkdtemp, rm, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import { normalizeFileInput } from "./files.js";
import type { FileInput } from "./types/documents.js";

describe("normalizeFileInput", () => {
  it("normalizes blobs and files", async () => {
    const blob = await normalizeFileInput(new Blob(["hello"]));
    const file = await normalizeFileInput(new File(["hello"], "note.txt"));

    await expect(blob.blob.text()).resolves.toBe("hello");
    expect(blob.name).toBe("document");
    await expect(file.blob.text()).resolves.toBe("hello");
    expect(file.name).toBe("note.txt");
  });

  it("normalizes bytes and buffers", async () => {
    const bytes = await normalizeFileInput(new Uint8Array([104, 105]));
    const buffer = await normalizeFileInput(Buffer.from("ok"));

    await expect(bytes.blob.text()).resolves.toBe("hi");
    expect(bytes.name).toBe("document");
    await expect(buffer.blob.text()).resolves.toBe("ok");
    expect(buffer.name).toBe("document");
  });

  it("normalizes path inputs with default and explicit filenames", async () => {
    const dir = await mkdtemp(join(tmpdir(), "bigrag-files-"));
    const path = join(dir, "note.txt");
    await writeFile(path, "hello");

    try {
      const inferred = await normalizeFileInput({ path });
      const explicit = await normalizeFileInput({ path, name: "renamed.txt" });

      await expect(inferred.blob.text()).resolves.toBe("hello");
      expect(inferred.name).toBe("note.txt");
      await expect(explicit.blob.text()).resolves.toBe("hello");
      expect(explicit.name).toBe("renamed.txt");
    } finally {
      await rm(dir, { recursive: true, force: true });
    }
  });

  it("rejects unsupported inputs", async () => {
    await expect(normalizeFileInput(42 as unknown as FileInput)).rejects.toThrow(
      "Unsupported file input type",
    );
  });
});
