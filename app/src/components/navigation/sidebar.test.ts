import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { Sidebar } from "./sidebar";

const routerState = vi.hoisted(() => ({ pathname: "/settings" }));

vi.mock("@tanstack/react-router", () => ({
  Link: ({
    children,
    className,
    to,
    ...props
  }: {
    children?: ReactNode;
    className?: string;
    to: string;
  }) => createElement("a", { className, href: to, ...props }, children),
  useRouterState: ({ select }: { select: (state: { location: { pathname: string } }) => string }) =>
    select({ location: { pathname: routerState.pathname } }),
}));

vi.mock("./user-menu", () => ({
  UserMenu: () => createElement("div", null, "Yoginth"),
}));

describe("sidebar navigation", () => {
  it("keeps admin-only destinations out of member navigation", () => {
    const html = renderToStaticMarkup(createElement(Sidebar, { role: "member" }));

    expect(html).toContain("Overview");
    expect(html).toContain("Collections");
    expect(html).not.toContain("Usage");
    expect(html).not.toContain("Audit");
    expect(html).not.toContain("Connectors");
    expect(html).not.toContain("Backups");
    expect(html).not.toContain("Vector Storage");
    expect(html).not.toContain("Settings");
  });

  it("groups admin destinations by sidebar section", () => {
    const html = renderToStaticMarkup(createElement(Sidebar, { role: "admin" }));

    expect(html).toContain("Workspace");
    expect(html).toContain("Interfaces");
    expect(html).toContain("Observability");
    expect(html).toContain("Administration");
    expect(html).toContain("Usage");
    expect(html).toContain("Audit");
    expect(html).toContain("Connectors");
    expect(html).toContain("Backups");
    expect(html).toContain("Vector Storage");
    expect(html.indexOf("Usage")).toBeGreaterThan(html.indexOf("Access Logs"));
    expect(html.indexOf("Audit")).toBeGreaterThan(html.indexOf("Usage"));
    expect(html.indexOf("Connectors")).toBeGreaterThan(html.indexOf("Webhooks"));
    expect(html.indexOf("Backups")).toBeGreaterThan(html.indexOf("Connectors"));
    expect(html.indexOf("Vector Storage")).toBeGreaterThan(html.indexOf("Backups"));
    expect(html.indexOf("Usage")).toBeLessThan(html.indexOf("Settings"));
    expect(html.indexOf("Audit")).toBeLessThan(html.indexOf("Settings"));
    expect(html.indexOf("Connectors")).toBeLessThan(html.indexOf("Settings"));
    expect(html.indexOf("Backups")).toBeLessThan(html.indexOf("Settings"));
    expect(html.indexOf("Vector Storage")).toBeLessThan(html.indexOf("Settings"));
  });

  it("matches active routes by exact path or descendants", () => {
    const activeLinkPattern = (href: string) =>
      new RegExp(`<a(?=[^>]*href="${href}")(?=[^>]*aria-current="page")[^>]*>`);

    routerState.pathname = "/connectors";
    expect(renderToStaticMarkup(createElement(Sidebar, { role: "admin" }))).toMatch(
      activeLinkPattern("/connectors"),
    );

    routerState.pathname = "/connectors/google";
    expect(renderToStaticMarkup(createElement(Sidebar, { role: "admin" }))).toMatch(
      activeLinkPattern("/connectors"),
    );

    routerState.pathname = "/collections/docs/connectors";
    expect(renderToStaticMarkup(createElement(Sidebar, { role: "admin" }))).not.toMatch(
      activeLinkPattern("/connectors"),
    );

    routerState.pathname = "/vector-storage";
    expect(renderToStaticMarkup(createElement(Sidebar, { role: "admin" }))).toMatch(
      activeLinkPattern("/vector-storage"),
    );
  });

  it("leaves a bottom inset on the desktop sidebar shell", () => {
    const html = renderToStaticMarkup(createElement(Sidebar, { role: "admin" }));

    expect(html).toContain("hidden h-[calc(100dvh-1rem)] w-60");
    expect(html).not.toContain("hidden h-full w-60");
  });
});
