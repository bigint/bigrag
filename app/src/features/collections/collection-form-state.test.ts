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
  it("creates defaults", () => {
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

  it("slugifies collection names and builds create payloads", () => {
    expect(slugifyCollectionName("Product Docs!! 2026")).toBe("product_docs_2026");
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

  it("validates create and search values", () => {
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
      validateCollectionSearchFormValues({
        mode: "semantic",
        query: " ",
        rerank: false,
        topK: 5,
      }),
    ).toBe("Query is required");
    expect(
      collectionSearchBodyFromValues({
        mode: "hybrid",
        query: "docs",
        rerank: true,
        topK: 7,
      }),
    ).toEqual({ query: "docs", rerank: true, search_mode: "hybrid", top_k: 7 });
  });
});
