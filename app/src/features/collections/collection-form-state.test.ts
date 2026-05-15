import { describe, expect, it } from "vitest";
import {
  collectionSearchBodyFromValues,
  createCollectionBodyFromValues,
  defaultCollectionSearchFormValues,
  defaultCreateCollectionFormValues,
  slugifyCollectionName,
  validateCollectionSearchFormValues,
  validateCreateCollectionFormValues,
} from "./collection-form-state";

describe("collection form state", () => {
  it("builds defaults for collection create and search forms", () => {
    expect(defaultCreateCollectionFormValues()).toEqual({
      chunkOverlap: 50,
      chunkSize: 512,
      description: "",
      name: "",
      presetId: "",
    });
    expect(defaultCollectionSearchFormValues()).toEqual({
      mode: "semantic",
      query: "",
      rerank: false,
      topK: 5,
    });
  });

  it("slugifies collection names the same way the UI submit did", () => {
    expect(slugifyCollectionName(" My Test.Collection! ")).toBe("_my_testcollection_");
    expect(slugifyCollectionName("A".repeat(60))).toHaveLength(48);
  });

  it("validates create collection values", () => {
    expect(validateCreateCollectionFormValues(defaultCreateCollectionFormValues())).toBe(
      "Name is required",
    );
    expect(
      validateCreateCollectionFormValues({
        ...defaultCreateCollectionFormValues(),
        name: "docs",
      }),
    ).toBe("Pick an embedding preset first");
    expect(
      validateCreateCollectionFormValues({
        chunkOverlap: 0,
        chunkSize: 127,
        description: "",
        name: "docs",
        presetId: "preset_1",
      }),
    ).toBe("Chunk size must be between 128 and 10000");
  });

  it("validates and builds search payloads", () => {
    expect(validateCollectionSearchFormValues(defaultCollectionSearchFormValues())).toBe(
      "Query is required",
    );
    expect(
      validateCollectionSearchFormValues({
        mode: "semantic",
        query: "docs",
        rerank: false,
        topK: 51,
      }),
    ).toBe("Top K must be between 1 and 50");
    expect(
      collectionSearchBodyFromValues({
        mode: "hybrid",
        query: "  docs  ",
        rerank: true,
        topK: 7,
      }),
    ).toEqual({
      query: "  docs  ",
      rerank: true,
      search_mode: "hybrid",
      top_k: 7,
    });
  });

  it("builds create collection payloads with slugged names", () => {
    expect(
      createCollectionBodyFromValues({
        chunkOverlap: 25,
        chunkSize: 256,
        description: "Docs",
        name: "Product Docs",
        presetId: "preset_1",
      }),
    ).toEqual({
      chunk_overlap: 25,
      chunk_size: 256,
      description: "Docs",
      embedding_preset_id: "preset_1",
      name: "product_docs",
    });
  });
});
