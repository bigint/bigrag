import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { StatusPage } from "./status-page";

describe("StatusPage", () => {
  it("renders the status code, copy, and actions", () => {
    const html = renderToStaticMarkup(
      <StatusPage code="404" description="Missing workspace route" title="Page not found">
        <span>Overview</span>
      </StatusPage>,
    );

    expect(html).toContain("404");
    expect(html).toContain("Page not found");
    expect(html).toContain("Missing workspace route");
    expect(html).toContain("Overview");
  });
});
