import { createElement, type ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { UserMenu } from "./user-menu";

vi.mock("@base-ui/react/menu", () => ({
  Menu: {
    Item: ({
      children,
      className,
      onClick,
    }: {
      children?: ReactNode;
      className?: string;
      onClick?: () => void;
    }) => createElement("button", { className, onClick, type: "button" }, children),
    Popup: ({ children, className }: { children?: ReactNode; className?: string }) =>
      createElement("div", { className }, children),
    Portal: ({ children }: { children?: ReactNode }) => createElement("div", null, children),
    Positioner: ({
      align,
      children,
      className,
      side,
      sideOffset,
    }: {
      align?: string;
      children?: ReactNode;
      className?: string;
      side?: string;
      sideOffset?: number;
    }) =>
      createElement(
        "div",
        { className, "data-align": align, "data-side": side, "data-side-offset": sideOffset },
        children,
      ),
    Root: ({ children }: { children?: ReactNode }) => createElement("div", null, children),
    Trigger: ({
      children,
      className,
      title,
    }: {
      children?: ReactNode;
      className?: string;
      title?: string;
    }) => createElement("button", { className, title, type: "button" }, children),
  },
}));

vi.mock("@tanstack/react-router", () => ({
  useNavigate: () => vi.fn(),
}));

vi.mock("@/hooks/use-auth", () => ({
  useLogout: () => ({ mutateAsync: vi.fn() }),
  useSession: () => ({
    data: {
      user: {
        display_name: "Yoginth",
        email: "yoginth@hey.com",
      },
    },
  }),
}));

describe("user menu", () => {
  it("centers the desktop sign out menu over the sidebar footer", () => {
    const html = renderToStaticMarkup(createElement(UserMenu));

    expect(html).toContain('data-align="center"');
    expect(html).toContain('data-side="top"');
  });

  it("keeps the compact menu attached to the right side", () => {
    const html = renderToStaticMarkup(createElement(UserMenu, { compact: true }));

    expect(html).toContain('data-align="start"');
    expect(html).toContain('data-side="right"');
  });
});
