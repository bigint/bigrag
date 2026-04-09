import {
  FileSearch,
  FileText,
  Layers,
  Search,
  Upload,
  Webhook,
} from "lucide-react";
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
      "OpenAI and Cohere embedding models with per-collection configuration. Mix providers across collections.",
    href: "/docs/concepts/embeddings",
    icon: <Layers className="size-5" />,
    title: "Any Embedding Model",
  },
  {
    description:
      "Semantic, keyword, or hybrid search with Reciprocal Rank Fusion. Optional Cohere reranking for top results.",
    href: "/docs/concepts/search",
    icon: <Search className="size-5" />,
    title: "Hybrid Search",
  },
  {
    description:
      "Stream document processing progress via Server-Sent Events. Track parsing, chunking, and embedding in real time.",
    href: "/docs/api-reference/documents",
    icon: <Upload className="size-5" />,
    title: "Real-Time Progress",
  },
  {
    description:
      "HMAC-signed webhook payloads with automatic retries. Get notified when documents are processed or fail.",
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

export function FeatureCard({
  icon,
  title,
  description,
  href,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  href: string;
}) {
  return (
    <Link
      className="group relative rounded-xl border border-fd-border bg-fd-card p-6 transition-all duration-200 hover:border-fd-foreground/15 hover:shadow-sm"
      href={href}
    >
      <div className="mb-4 inline-flex rounded-lg border border-fd-border bg-fd-background p-2.5 text-fd-foreground transition-colors group-hover:border-fd-foreground/15 group-hover:bg-fd-accent">
        {icon}
      </div>
      <h3 className="mb-2 text-[15px] font-semibold text-fd-foreground">{title}</h3>
      <p className="text-sm leading-relaxed text-fd-muted-foreground">{description}</p>
    </Link>
  );
}
