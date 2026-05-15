import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { AuditPage } from "./audit-page";

type AuditHookOptions = {
  queryFn: () => Promise<unknown>;
  queryKey: readonly unknown[];
  path: string;
};

const auditState = vi.hoisted(() => ({
  value: {
    data: {
      entries: Array.from({ length: 25 }, (_, index) => ({
        id: `audit_${index}`,
        actor_id: "user_1",
        actor_email: "admin@example.com",
        api_key_id: null,
        action: "api_key.create",
        resource_type: "api_key",
        resource_id: `key_${index}`,
        metadata: {},
        ip: "127.0.0.1",
        user_agent: null,
        created_at: "2026-05-15T12:00:00Z",
      })),
      total: 63,
    },
    error: null,
    isPending: false,
  },
}));

const auditHookOptions = vi.hoisted((): AuditHookOptions[] => []);
const getAudit = vi.hoisted(() => vi.fn(async () => ({ entries: [], total: 0 })));

vi.mock("@/hooks/use-sse-snapshot-query", () => ({
  useSseSnapshotQuery: (options: AuditHookOptions) => {
    auditHookOptions.push(options);
    return auditState.value;
  },
}));

vi.mock("@/lib/api", () => ({
  apiClient: {
    get: getAudit,
  },
}));

beforeEach(() => {
  auditHookOptions.length = 0;
  getAudit.mockClear();
});

describe("AuditPage", () => {
  it("requests the first audit page and renders page buttons", async () => {
    const html = renderToStaticMarkup(<AuditPage />);
    const options = auditHookOptions[0];

    expect(options.queryKey).toEqual(["audit", "list", { limit: 25, offset: 0 }]);
    expect(options.path).toBe("v1/admin/realtime/audit?limit=25&offset=0");

    await options.queryFn();

    expect(getAudit).toHaveBeenCalledWith("v1/admin/audit", { limit: 25, offset: 0 });
    expect(html).toContain("Showing 1-25 of 63 entries");
    expect(html).toContain("Page 1 of 3");
    expect(html).toContain("Previous");
    expect(html).toContain("Next");
    expect(html).toMatch(/disabled="" aria-label="Previous audit page"/);
    expect(html).not.toMatch(/disabled="" aria-label="Next audit page"/);
  });
});
