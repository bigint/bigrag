"use client";

import { useEffect, useRef } from "react";

export function Mermaid({ chart }: { chart: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);

  useEffect(() => {
    const currentRender = ++renderIdRef.current;

    const render = async () => {
      const { default: mermaid } = await import("mermaid");
      const isDark = document.documentElement.classList.contains("dark");

      mermaid.initialize({
        fontFamily:
          "ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
        startOnLoad: false,
        theme: "base",
        themeVariables: isDark
          ? {
              // Dark mode
              actorBkg: "#1a1a1a",
              actorBorder: "#333",
              actorLineColor: "#555",
              actorTextColor: "#e5e5e5",
              background: "transparent",
              clusterBkg: "#1a1a1a",
              clusterBorder: "#333",
              edgeLabelBackground: "#141414",
              fontSize: "13px",
              labelTextColor: "#e5e5e5",
              lineColor: "#444",
              loopTextColor: "#999",
              mainBkg: "#1a1a1a",
              mainContrastColor: "#e5e5e5",
              nodeBorder: "#333",
              nodeTextColor: "#e5e5e5",
              noteBkgColor: "#1a1a1a",
              noteBorderColor: "#333",
              noteTextColor: "#ccc",
              primaryBorderColor: "#333",
              primaryColor: "#1a1a1a",
              primaryTextColor: "#e5e5e5",
              secondaryBorderColor: "#333",
              secondaryColor: "#222",
              secondaryTextColor: "#ccc",
              signalColor: "#888",
              signalTextColor: "#e5e5e5",
              tertiaryBorderColor: "#333",
              tertiaryColor: "#1a1a1a",
              tertiaryTextColor: "#ccc",
              textColor: "#e5e5e5"
            }
          : {
              // Light mode
              actorBkg: "#fff",
              actorBorder: "#e0e0e0",
              actorLineColor: "#ccc",
              actorTextColor: "#1a1a1a",
              background: "transparent",
              clusterBkg: "#fafafa",
              clusterBorder: "#e0e0e0",
              edgeLabelBackground: "#fff",
              fontSize: "13px",
              labelTextColor: "#1a1a1a",
              lineColor: "#ccc",
              loopTextColor: "#666",
              mainBkg: "#fff",
              mainContrastColor: "#1a1a1a",
              nodeBorder: "#e0e0e0",
              nodeTextColor: "#1a1a1a",
              noteBkgColor: "#fafafa",
              noteBorderColor: "#e0e0e0",
              noteTextColor: "#333",
              primaryBorderColor: "#e0e0e0",
              primaryColor: "#fff",
              primaryTextColor: "#1a1a1a",
              secondaryBorderColor: "#e0e0e0",
              secondaryColor: "#fafafa",
              secondaryTextColor: "#333",
              signalColor: "#666",
              signalTextColor: "#1a1a1a",
              tertiaryBorderColor: "#e0e0e0",
              tertiaryColor: "#f5f5f5",
              tertiaryTextColor: "#333",
              textColor: "#1a1a1a"
            }
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

    render();
  }, [chart]);

  return (
    <div className="not-prose my-8 overflow-hidden rounded-xl border border-fd-border bg-fd-card">
      <div
        className="flex justify-center overflow-x-auto px-6 py-8 [&_svg]:max-w-full"
        ref={ref}
      />
    </div>
  );
}
