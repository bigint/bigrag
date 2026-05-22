import { Database, FileSearch, FileText, Layers, Search, Webhook } from "lucide-react";
import Link from "next/link";
import type { ReactNode } from "react";

export const features = [
  {
    description:
      "PDF, DOCX, PPTX, HTML, Markdown, images with OCR, and more — powered by Docling for universal document parsing.",
    href: "/docs/concepts/documents",
    icon: <FileText className="size-5" />,
    title: "Any Document Format",
  },
  {
    description:
      "OpenAI, Cohere, Voyage, and OpenAI-compatible models with per-collection configuration. Mix providers across collections.",
    href: "/docs/concepts/embeddings",
    icon: <Layers className="size-5" />,
    title: "Any Embedding Model",
  },
  {
    description:
      "Turbopuffer powers semantic, keyword, and hybrid search from the same chunk store, with Reciprocal Rank Fusion for mixed queries.",
    href: "/docs/concepts/search",
    icon: <Search className="size-5" />,
    title: "Turbopuffer Search",
  },
  {
    description:
      "Each collection maps to a Turbopuffer namespace, keeping vector writes, keyword indexes, exports, and deletes scoped.",
    href: "/docs/concepts/collections",
    icon: <Database className="size-5" />,
    title: "Namespace Isolation",
  },
  {
    description:
      "HMAC-signed webhook payloads with automatic retries for document, collection, connector, and backup events.",
    href: "/docs/concepts/webhooks",
    icon: <Webhook className="size-5" />,
    title: "Webhooks",
  },
  {
    description:
      "Zero-dependency TypeScript client for Node.js, browsers, Deno, and Bun. Full type safety and automatic retries.",
    href: "/docs/sdks/typescript",
    icon: <FileSearch className="size-5" />,
    title: "TypeScript SDK",
  },
];

export const FeatureCard = ({
  icon,
  title,
  description,
  href,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  href: string;
}) => (
  <Link
    className="group relative rounded-lg border border-fd-border bg-fd-card p-6 hover:border-fd-foreground/15 hover:shadow-sm"
    href={href}
  >
    <div className="mb-4 inline-flex rounded-md border border-fd-border bg-fd-background p-2.5 text-fd-foreground group-hover:border-fd-foreground/15 group-hover:bg-fd-accent">
      {icon}
    </div>
    <h3 className="mb-2 text-[15px] font-semibold text-fd-foreground">{title}</h3>
    <p className="text-sm leading-relaxed text-fd-muted-foreground">{description}</p>
  </Link>
);
