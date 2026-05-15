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
          default: false,
          description: "Require secure session cookies.",
          group: "security",
          key: "session_cookie_secure",
          kind: "bool",
          label: "Secure cookies",
          max: null,
          min: null,
          options: [],
          secret: false,
        },
        {
          default: null,
          description: "Optional cookie domain.",
          group: "security",
          key: "session_cookie_domain",
          kind: "string",
          label: "Session cookie domain",
          max: null,
          min: null,
          options: [],
          secret: false,
        },
      ],
      values: {
        session_cookie_domain: {
          has_value: true,
          key: "session_cookie_domain",
          source: "database",
          updated_at: null,
          updated_by: null,
          value: "",
        },
        session_cookie_secure: {
          has_value: true,
          key: "session_cookie_secure",
          source: "database",
          updated_at: null,
          updated_by: null,
          value: true,
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

    expect(html).toContain('placeholder=".example.com"');
  });

  it("can render a focused subset of settings", () => {
    const html = renderToStaticMarkup(
      <InstanceSettingsTab group="security" includeKeys={["session_cookie_domain"]} />,
    );

    expect(html).toContain("Session cookie domain");
    expect(html).not.toContain("Secure cookies");
  });
});
