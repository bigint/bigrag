import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { VectorStoragePage } from "./vector-storage-page";

const renderedGroups = vi.hoisted((): string[] => []);

vi.mock("@/features/settings/tabs/instance-settings-tab", () => ({
  InstanceSettingsTab: ({ group }: { readonly group: string }) => {
    renderedGroups.push(group);
    return <section>{group}</section>;
  },
}));

describe("VectorStoragePage", () => {
  it("renders vector storage as its own runtime surface", () => {
    renderedGroups.length = 0;

    const html = renderToStaticMarkup(<VectorStoragePage />);

    expect(html).toContain("Vector Storage");
    expect(html).toContain("Choose the instance-level vector backend");
    expect(renderedGroups).toEqual(["vector_store"]);
  });
});
