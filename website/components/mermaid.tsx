"use client";

import { useEffect, useId, useRef, useState } from "react";
import { mermaidThemeVariables } from "./mermaid-themes";

type MermaidProps = {
  chart: string;
  title?: string;
};

export const Mermaid = ({ chart, title = "Diagram" }: MermaidProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);
  const mermaidId = useId().replaceAll(":", "");
  const [error, setError] = useState<string | null>(null);

  useMermaidRender(chart, ref, renderIdRef, mermaidId, setError);

  return (
    <figure className="not-prose my-10 overflow-hidden rounded-lg border border-fd-border bg-fd-card shadow-sm">
      <figcaption className="sr-only">{title}</figcaption>
      <div className="overflow-x-auto px-4 py-6 sm:px-6 sm:py-8">
        <div
          aria-label={title}
          className="mx-auto min-w-[56rem] max-w-[72rem] [&_svg]:h-auto [&_svg]:w-full"
          ref={ref}
          role="img"
        />
      </div>
      {error ? (
        <div className="border-t border-fd-border bg-fd-background px-4 py-3 text-fd-muted-foreground text-sm sm:px-6">
          Unable to render this diagram.
        </div>
      ) : null}
    </figure>
  );
};

const useMermaidRender = (
  chart: string,
  ref: { current: HTMLDivElement | null },
  renderIdRef: { current: number },
  mermaidId: string,
  setError: (error: string | null) => void,
) => {
  useEffect(() => {
    const currentRender = ++renderIdRef.current;

    const render = async () => {
      try {
        setError(null);

        const { default: mermaid } = await import("mermaid");

        mermaid.initialize({
          fontFamily:
            "var(--font-outfit), ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
          startOnLoad: false,
          theme: "base",
          themeVariables: mermaidThemeVariables,
        });

        if (currentRender !== renderIdRef.current || !ref.current) return;

        const { svg } = await mermaid.render(`mermaid-${mermaidId}-${currentRender}`, chart);

        if (currentRender !== renderIdRef.current || !ref.current) return;

        while (ref.current.firstChild) {
          ref.current.removeChild(ref.current.firstChild);
        }

        const parser = new DOMParser();
        const doc = parser.parseFromString(svg, "image/svg+xml");
        const svgElement = doc.documentElement;
        ref.current.appendChild(svgElement);
      } catch (renderError) {
        if (currentRender !== renderIdRef.current) return;
        setError(renderError instanceof Error ? renderError.message : "Render failed");
      }
    };

    void render();
  }, [chart, mermaidId, ref, renderIdRef, setError]);
};
