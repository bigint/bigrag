import type { ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { AppErrorPage, AppNotFoundPage } from "./status-page";

vi.mock("@tanstack/react-router", async () => {
  const React = await import("react");
  return {
    Link: ({ children, to, ...props }: { children?: ReactNode; className?: string; to?: string }) =>
      React.createElement("a", { ...props, href: to }, children),
  };
});

describe("StatusPage", () => {
  it("renders the status code, copy, and actions", () => {
    const html = renderToStaticMarkup(<AppNotFoundPage />);

    expect(html).toContain("404");
    expect(html).toContain("Page not found");
    expect(html).toContain("This admin route does not exist.");
    expect(html).toContain("Overview");
  });

  it("renders readable route error details on the 500 page", () => {
    const error = new Error("Vector storage credentials failed validation", {
      cause: new Error("turbopuffer rejected the configured API key"),
    });

    const html = renderToStaticMarkup(<AppErrorPage error={error} reset={() => undefined} />);

    expect(html).toContain("500");
    expect(html).toContain("Error details");
    expect(html).toContain("Vector storage credentials failed validation");
    expect(html).toContain("turbopuffer rejected the configured API key");
    expect(html).toContain("Try again");
  });
});
