"use client";

import { useEffect, useRef } from "react";
import { mermaidThemeVariables } from "./mermaid-themes";

export const Mermaid = ({ chart }: { chart: string }) => {
  const ref = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);

  useMermaidRender(chart, ref, renderIdRef);

  return (
    <div className="not-prose my-8 overflow-hidden rounded-xl border border-fd-border bg-fd-card">
      <div className="flex justify-center overflow-x-auto px-6 py-8 [&_svg]:max-w-full" ref={ref} />
    </div>
  );
};

const useMermaidRender = (
  chart: string,
  ref: { current: HTMLDivElement | null },
  renderIdRef: { current: number },
) => {
  useEffect(() => {
    const currentRender = ++renderIdRef.current;

    const render = async () => {
      const { default: mermaid } = await import("mermaid");

      mermaid.initialize({
        fontFamily: "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        startOnLoad: false,
        theme: "base",
        themeVariables: mermaidThemeVariables,
      });

      if (currentRender !== renderIdRef.current || !ref.current) return;

      const id = `mermaid-${Math.random().toString(36).slice(2, 9)}`;
      const { svg } = await mermaid.render(id, chart);

      if (currentRender !== renderIdRef.current || !ref.current) return;

      while (ref.current.firstChild) {
        ref.current.removeChild(ref.current.firstChild);
      }

      const parser = new DOMParser();
      const doc = parser.parseFromString(svg, "image/svg+xml");
      const svgElement = doc.documentElement;
      ref.current.appendChild(svgElement);
    };

    void render();
  }, [chart, ref, renderIdRef]);
};
