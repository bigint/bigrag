import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { VectorStoragePage } from "./vector-storage-page";

const renderedPanels = vi.hoisted(
  (): Array<{
    group: string;
    includeKeys?: readonly string[];
    title?: string;
  }> => [],
);

vi.mock("@/features/settings/tabs/instance-settings-tab", () => ({
  InstanceSettingsTab: ({
    group,
    includeKeys,
    layoutOverride,
  }: {
    readonly group: string;
    readonly includeKeys?: readonly string[];
    readonly layoutOverride?: { readonly title?: string };
  }) => {
    renderedPanels.push({
      group,
      includeKeys,
      title: layoutOverride?.title,
    });
    return <section>{layoutOverride?.title}</section>;
  },
}));

describe("VectorStoragePage", () => {
  it("renders provider tabs using Qdrant first", () => {
    renderedPanels.length = 0;

    const html = renderToStaticMarkup(<VectorStoragePage />);

    expect(html).toContain("Vector Storage");
    expect(html).toContain("Collections choose Qdrant or turbopuffer");
    expect(html).toContain("Qdrant");
    expect(html).toContain("turbopuffer");
    expect(renderedPanels).toEqual([
      {
        group: "vector_store",
        includeKeys: [
          "qdrant_url",
          "qdrant_connect_timeout_seconds",
          "qdrant_required",
          "qdrant_search_ef",
        ],
        title: "Qdrant",
      },
    ]);
  });

  it("uses requested provider tabs", () => {
    renderedPanels.length = 0;

    renderToStaticMarkup(<VectorStoragePage provider="turbopuffer" />);

    expect(renderedPanels).toEqual([
      {
        group: "vector_store",
        includeKeys: ["turbopuffer_api_key", "turbopuffer_region", "turbopuffer_namespace_prefix"],
        title: "turbopuffer",
      },
    ]);
  });

  it("falls back to Qdrant for unsupported vector storage providers", () => {
    renderedPanels.length = 0;

    renderToStaticMarkup(<VectorStoragePage provider="pinecone" />);

    expect(renderedPanels).toEqual([
      {
        group: "vector_store",
        includeKeys: [
          "qdrant_url",
          "qdrant_connect_timeout_seconds",
          "qdrant_required",
          "qdrant_search_ef",
        ],
        title: "Qdrant",
      },
    ]);
  });
});
