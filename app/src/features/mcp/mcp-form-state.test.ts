import { describe, expect, it } from "vitest";
import {
  MCP_UNSCOPED,
  defaultMcpCreateFormValues,
  mcpCreateBodyFromValues,
  mcpServerNameFromTitle,
  slugifyMcpServerName,
  validateMcpCreateFormValues,
} from "./mcp-form-state";

describe("mcp form state", () => {
  it("defaults to an unscoped server", () => {
    expect(defaultMcpCreateFormValues()).toEqual({
      collection: MCP_UNSCOPED,
      serverName: "",
      title: "",
    });
  });

  it("slugifies server names from titles", () => {
    expect(slugifyMcpServerName(" Product Docs MCP! ")).toBe("product-docs-mcp");
    expect(mcpServerNameFromTitle("!!!")).toBe("bigrag");
    expect(slugifyMcpServerName("a".repeat(80))).toHaveLength(60);
  });

  it("validates required title and server name fields", () => {
    expect(
      validateMcpCreateFormValues({
        collection: MCP_UNSCOPED,
        serverName: "",
        title: " ",
      }),
    ).toBe("Title is required");
    expect(
      validateMcpCreateFormValues({
        collection: MCP_UNSCOPED,
        serverName: "",
        title: "Docs",
      }),
    ).toBe("Server name is required");
  });

  it("preserves the create payload shape", () => {
    expect(
      mcpCreateBodyFromValues({
        collection: MCP_UNSCOPED,
        serverName: "docs",
        title: "Docs",
      }),
    ).toEqual({
      collection: null,
      server_name: "docs",
      title: "Docs",
    });
    expect(
      mcpCreateBodyFromValues({
        collection: "docs",
        serverName: "docs",
        title: "Docs",
      }),
    ).toEqual({
      collection: "docs",
      server_name: "docs",
      title: "Docs",
    });
  });
});
