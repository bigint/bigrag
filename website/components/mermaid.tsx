"use client";

import { useEffect, useRef, useState } from "react";
import { mermaidThemeVariables } from "./mermaid-themes";

type MermaidProps = {
  chart: string;
  title?: string;
};

export const Mermaid = ({ chart, title = "Diagram" }: MermaidProps) => {
  const ref = useRef<HTMLDivElement>(null);
  const renderIdRef = useRef(0);
  const [hasError, setHasError] = useState(false);

  useMermaidRender(chart, ref, renderIdRef, setHasError);

  return (
    <figure className="not-prose my-10 overflow-hidden rounded-lg border border-fd-border bg-fd-card shadow-sm">
      <figcaption className="sr-only">{title}</figcaption>
      <div className="overflow-x-auto px-4 py-6 sm:px-6 sm:py-8">
        <div
          aria-label={title}
          className="mx-auto min-w-[56rem] max-w-[64rem] [&_svg]:!max-w-none [&_svg]:h-auto [&_svg]:w-full"
          ref={ref}
          role="img"
        />
      </div>
      {hasError ? (
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
  setHasError: (hasError: boolean) => void,
) => {
  useEffect(() => {
    const currentRender = ++renderIdRef.current;

    const render = async () => {
      try {
        setHasError(false);

        const { default: mermaid } = await import("mermaid");

        mermaid.initialize({
          fontFamily:
            "var(--font-outfit), ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, sans-serif",
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

        const template = document.createElement("template");
        template.innerHTML = svg.trim();
        const svgElement = template.content.querySelector("svg");

        if (!svgElement) {
          setHasError(true);
          return;
        }

        ref.current.appendChild(svgElement);
      } catch {
        if (currentRender !== renderIdRef.current) return;
        setHasError(true);
      }
    };

    void render();
  }, [chart, ref, renderIdRef, setHasError]);
};
