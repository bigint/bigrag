import { describe, expect, it } from "vitest";
import {
  defaultMcpCreateFormValues,
  MCP_UNSCOPED,
  mcpCreateBodyFromValues,
  mcpServerNameFromTitle,
  slugifyMcpServerName,
  validateMcpCreateFormValues,
} from "./mcp-form-state";

describe("mcp form state", () => {
  it("creates defaults and server names", () => {
    expect(defaultMcpCreateFormValues()).toEqual({
      collection: MCP_UNSCOPED,
      serverName: "",
      title: "",
    });
    expect(slugifyMcpServerName(" Product Docs!! ")).toBe("product-docs");
    expect(mcpServerNameFromTitle("")).toBe("bigrag");
  });

  it("validates and builds create payloads", () => {
    expect(
      validateMcpCreateFormValues({ collection: MCP_UNSCOPED, serverName: "", title: "" }),
    ).toBe("Title is required");
    expect(
      mcpCreateBodyFromValues({
        collection: "docs",
        serverName: "product-docs",
        title: "Product Docs",
      }),
    ).toEqual({
      collection: "docs",
      server_name: "product-docs",
      title: "Product Docs",
    });
  });
});
