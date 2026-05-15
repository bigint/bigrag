import type { CSSProperties, ReactNode } from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it, vi } from "vitest";
import { Select } from "./select";

type PrimitiveProps = {
  children?: ReactNode | ((value: string) => ReactNode);
  className?: string;
  placeholder?: string;
  style?: CSSProperties;
  value?: string;
};

vi.mock("@base-ui/react/select", async () => {
  const React = await import("react");
  const SelectContext = React.createContext("");
  const renderChildren = (children: PrimitiveProps["children"], value: string) =>
    typeof children === "function" ? children(value) : children;
  const primitive =
    (tag: keyof HTMLElementTagNameMap) =>
    ({ children, className, style, value }: PrimitiveProps) =>
      React.createElement(tag, { className, "data-value": value, style }, children);

  return {
    Select: {
      Root: ({ children, value = "" }: PrimitiveProps) => (
        <SelectContext.Provider value={value}>{children}</SelectContext.Provider>
      ),
      Trigger: primitive("button"),
      Value: ({ children, placeholder }: PrimitiveProps) => {
        const value = React.useContext(SelectContext);
        return <span>{renderChildren(children, value || placeholder || "")}</span>;
      },
      Icon: primitive("span"),
      Portal: ({ children }: PrimitiveProps) => <>{children}</>,
      Positioner: primitive("div"),
      Popup: primitive("div"),
      List: primitive("div"),
      Item: primitive("div"),
      ItemIndicator: primitive("span"),
      ItemText: primitive("span"),
    },
  };
});

describe("Select", () => {
  it("keeps dropdown option text aligned when an item is selected", () => {
    const html = renderToStaticMarkup(
      <Select
        value="30"
        onChange={() => undefined}
        options={[
          { label: "Last 7 days", value: "7" },
          { label: "Last 30 days", value: "30" },
        ]}
      />,
    );

    expect(html).toContain("relative flex w-full");
    expect(html).toContain("pr-8 text-sm");
    expect(html).toContain("pointer-events-none absolute right-3 inline-flex size-4");
    expect(html).toContain("min-w-0 flex-1 truncate");
  });
});
