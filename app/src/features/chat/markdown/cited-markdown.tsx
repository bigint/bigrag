import { Children, cloneElement, isValidElement, memo, type ReactNode, useMemo } from "react";
import ReactMarkdown, { type Components } from "react-markdown";
import remarkGfm from "remark-gfm";
import { cn } from "@/lib/cn";

const CITATION_RE = /\[([0-9]+(?:\s*,\s*[0-9]+)*)\]/g;
const MARKDOWN_PLUGINS = [remarkGfm];

const renderInlineCitations = (
  content: string,
  chunkCount: number,
  onCite: (n: number) => void,
): ReactNode[] => {
  const nodes: ReactNode[] = [];
  let last = 0;
  let key = 0;
  for (const match of content.matchAll(CITATION_RE)) {
    const idx = match.index ?? 0;
    if (idx > last) {
      nodes.push(<span key={`t-${key++}`}>{content.slice(last, idx)}</span>);
    }
    const citations = (match[1] ?? "")
      .split(",")
      .map((value) => Number.parseInt(value.trim(), 10))
      .filter((value) => Number.isFinite(value));
    const valid = citations.length > 0 && citations.every((n) => n >= 1 && n <= chunkCount);
    if (valid) {
      nodes.push(
        <span key={`c-${key++}`} className="inline-flex items-center gap-0.5">
          {citations.map((n) => (
            <button
              key={n}
              type="button"
              onClick={() => onCite(n)}
              className="mx-0.5 inline-flex items-center rounded-md border border-border bg-muted px-1.5 align-baseline font-mono text-xs font-semibold text-foreground hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              aria-label={`Jump to source ${n}`}
            >
              [{n}]
            </button>
          ))}
        </span>,
      );
    } else {
      nodes.push(<span key={`r-${key++}`}>{match[0]}</span>);
    }
    last = idx + match[0].length;
  }
  if (last < content.length) {
    nodes.push(<span key={`t-${key++}`}>{content.slice(last)}</span>);
  }
  return nodes;
};

type CitationChildProps = {
  children?: ReactNode;
};

const renderCitedChildren = (
  children: ReactNode,
  chunkCount: number,
  onCite: (n: number) => void,
): ReactNode =>
  Children.map(children, (child) => {
    if (typeof child === "string") {
      return renderInlineCitations(child, chunkCount, onCite);
    }
    if (!isValidElement<CitationChildProps>(child)) {
      return child;
    }
    if (child.type === "code" || child.type === "pre" || child.type === "a") {
      return child;
    }
    if (child.props.children === undefined) {
      return child;
    }
    return cloneElement(child, {
      children: renderCitedChildren(child.props.children, chunkCount, onCite),
    });
  });

const markdownComponents = (chunkCount: number, onCite: (n: number) => void): Components => ({
  a: ({ children, href }) => (
    <a
      className="font-semibold text-primary underline underline-offset-2 hover:text-primary/80"
      href={href}
      rel={href ? "noreferrer" : undefined}
      target={href ? "_blank" : undefined}
    >
      {children}
    </a>
  ),
  blockquote: ({ children }) => (
    <blockquote className="my-3 border-l-2 border-border pl-4 text-muted-foreground">
      {renderCitedChildren(children, chunkCount, onCite)}
    </blockquote>
  ),
  code: ({ children, className }) => (
    <code className={cn("rounded-md bg-muted px-1.5 py-0.5 font-mono text-[0.92em]", className)}>
      {children}
    </code>
  ),
  h1: ({ children }) => (
    <h1 className="mt-4 mb-2 text-xl font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h1>
  ),
  h2: ({ children }) => (
    <h2 className="mt-4 mb-2 text-lg font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h2>
  ),
  h3: ({ children }) => (
    <h3 className="mt-3 mb-1.5 text-base font-semibold leading-7">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h3>
  ),
  h4: ({ children }) => (
    <h4 className="mt-3 mb-1.5 text-sm font-semibold leading-6">
      {renderCitedChildren(children, chunkCount, onCite)}
    </h4>
  ),
  input: ({ checked }) => (
    <input
      checked={Boolean(checked)}
      className="mr-2 size-3.5 align-text-top"
      readOnly
      type="checkbox"
    />
  ),
  li: ({ children, className }) => (
    <li className={cn("pl-1", className)}>{renderCitedChildren(children, chunkCount, onCite)}</li>
  ),
  ol: ({ children, start }) => (
    <ol className="my-2 list-decimal space-y-1 pl-5" start={start}>
      {children}
    </ol>
  ),
  p: ({ children }) => <p className="my-2">{renderCitedChildren(children, chunkCount, onCite)}</p>,
  pre: ({ children }) => (
    <pre className="my-3 overflow-x-auto rounded-lg bg-muted p-3 text-sm leading-6 [&_code]:bg-transparent [&_code]:p-0">
      {children}
    </pre>
  ),
  table: ({ children }) => (
    <div className="my-3 overflow-x-auto rounded-lg border border-border">
      <table className="min-w-full border-collapse text-sm">{children}</table>
    </div>
  ),
  td: ({ children }) => (
    <td className="border-border border-t px-3 py-2 align-top">
      {renderCitedChildren(children, chunkCount, onCite)}
    </td>
  ),
  th: ({ children }) => (
    <th className="bg-muted px-3 py-2 text-left font-semibold">
      {renderCitedChildren(children, chunkCount, onCite)}
    </th>
  ),
  ul: ({ children }) => <ul className="my-2 list-disc space-y-1 pl-5">{children}</ul>,
});

export const MarkdownContent = memo(
  ({
    chunkCount,
    content,
    onCite,
  }: {
    chunkCount: number;
    content: string;
    onCite: (n: number) => void;
  }) => {
    const components = useMemo(() => markdownComponents(chunkCount, onCite), [chunkCount, onCite]);
    return (
      <ReactMarkdown components={components} remarkPlugins={MARKDOWN_PLUGINS}>
        {content}
      </ReactMarkdown>
    );
  },
);
MarkdownContent.displayName = "MarkdownContent";
