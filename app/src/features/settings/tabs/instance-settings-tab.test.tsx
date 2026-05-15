import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { InstanceSettingsTab } from "./instance-settings-tab";

const purgeEmbeddingCache = vi.hoisted(() => vi.fn());
const saveSettings = vi.hoisted(() => vi.fn());

vi.mock("@/hooks/use-instance-settings", () => ({
  useInstanceSettings: () => ({
    data: {
      specs: [
        {
          default: [],
          description: "Trusted proxy ranges.",
          group: "security",
          key: "trusted_proxies",
          kind: "string_list",
          label: "Trusted proxies",
          max: null,
          min: null,
          options: [],
          secret: false,
        },
        {
          default: "encrypted",
          description: "Persistent cache behavior.",
          group: "security",
          key: "embedding_cache_mode",
          kind: "select",
          label: "Embedding cache mode",
          max: null,
          min: null,
          options: ["encrypted", "disabled"],
          secret: false,
        },
      ],
      values: {
        embedding_cache_mode: {
          has_value: true,
          key: "embedding_cache_mode",
          source: "database",
          updated_at: null,
          updated_by: null,
          value: "encrypted",
        },
        trusted_proxies: {
          has_value: true,
          key: "trusted_proxies",
          source: "database",
          updated_at: null,
          updated_by: null,
          value: [],
        },
      },
    },
    isPending: false,
  }),
  usePurgeEmbeddingCache: () => ({
    isPending: false,
    mutate: purgeEmbeddingCache,
  }),
  useUpdateInstanceSettings: () => ({
    isPending: false,
    mutate: saveSettings,
  }),
}));

describe("InstanceSettingsTab", () => {
  it("renders save without standalone test or reset actions", () => {
    const html = renderToStaticMarkup(<InstanceSettingsTab group="security" />);

    expect(html).toContain(">Save changes<");
    expect(html).not.toContain(">Test<");
    expect(html).not.toContain(">Reset<");
  });

  it("renders placeholders for empty runtime inputs", () => {
    const html = renderToStaticMarkup(<InstanceSettingsTab group="security" />);

    expect(html).toContain('placeholder="10.0.0.0/8"');
  });

  it("can render a focused subset of settings", () => {
    const html = renderToStaticMarkup(
      <InstanceSettingsTab group="security" includeKeys={["embedding_cache_mode"]} />,
    );

    expect(html).toContain("Embedding cache mode");
    expect(html).not.toContain("Trusted proxies");
  });
});
