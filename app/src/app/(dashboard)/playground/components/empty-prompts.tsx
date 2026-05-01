"use client";

import {
  BookOpen,
  ChevronRight,
  Cpu,
  Database,
  FileSearch,
  KeyRound,
  MessageCircle,
  Plug,
} from "lucide-react";
import Link from "next/link";
import { Logo } from "@/components/brand/logo";

const ACTIONS = [
  { href: "/collections", icon: BookOpen, label: "Collections", span: "col-span-3" },
  { href: "/api-keys", icon: KeyRound, label: "API keys", span: "col-span-3" },
  { href: "/models", icon: Cpu, label: "Models", span: "col-span-2" },
  { href: "/mcp", icon: Plug, label: "MCP", span: "col-span-2" },
  { href: "/collections", icon: Database, label: "Ingest", span: "col-span-2" },
] as const;

const EXAMPLES = [
  {
    icon: FileSearch,
    text: "Summarize what this collection is about.",
  },
  {
    icon: MessageCircle,
    text: "What are the three most important concepts?",
  },
  {
    icon: Database,
    text: "Find references to a specific term.",
  },
  {
    icon: Cpu,
    text: "Compare two ideas mentioned in the docs.",
  },
  {
    icon: BookOpen,
    text: "Which source should I read first?",
  },
  {
    icon: Plug,
    text: "List the facts that need citations.",
  },
] as const;

interface Props {
  onSelect: (text: string) => void;
  disabled?: boolean;
}

export const EmptyPrompts = ({ onSelect, disabled }: Props) => {
  const time = new Intl.DateTimeFormat("en-IN", {
    hour: "numeric",
    minute: "2-digit",
  }).format(new Date());

  return (
    <div className="flex flex-1 items-start justify-center px-4 pt-[13vh] pb-8 text-center md:pt-[17vh]">
      <div className="mx-auto w-full max-w-[640px]">
        <Logo className="mx-auto mb-5 scale-110 justify-center" withWordmark={false} />
        <p className="text-[12px] font-medium text-muted-foreground">{time}</p>
        <h2 className="mt-2 text-[26px] font-semibold leading-tight tracking-normal">
          Your RAG Worker
        </h2>
        <p className="mx-auto mt-2 max-w-[360px] text-[13px] leading-5 text-muted-foreground">
          Ask a collection and get grounded answers with source citations.
        </p>

        <div className="mt-5 grid w-full grid-cols-6 gap-1.5">
          {ACTIONS.map((action) => {
            const Icon = action.icon;
            return (
              <Link
                key={action.label}
                href={action.href}
                className={`${action.span} inline-flex min-h-9 items-center justify-center gap-2 rounded-full border border-border bg-background px-3 text-[12px] font-semibold shadow-[0_8px_28px_rgba(0,0,0,0.035)] transition-[border-color,box-shadow,transform] hover:border-neutral-200 hover:shadow-[0_10px_32px_rgba(0,0,0,0.06)] active:scale-[0.99]`}
              >
                <Icon className="size-3.5 text-muted-foreground" />
                <span className="truncate">{action.label}</span>
              </Link>
            );
          })}
        </div>

        <div className="mt-4 w-full overflow-hidden rounded-[18px] border border-border bg-background text-left shadow-[0_12px_40px_rgba(0,0,0,0.035)]">
          <div className="border-b border-border px-4 py-2.5 text-[12px] font-semibold text-muted-foreground">
            Watch workflows
          </div>
          <div className="divide-y divide-border">
            {EXAMPLES.map((example) => {
              const Icon = example.icon;
              return (
                <button
                  disabled={disabled}
                  key={example.text}
                  onClick={() => onSelect(example.text)}
                  type="button"
                  className="flex min-h-8 w-full items-center gap-2 px-4 py-2 text-left text-[12px] font-semibold transition-colors hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
                >
                  <Icon className="size-3.5 shrink-0 text-muted-foreground" />
                  <span className="min-w-0 flex-1 truncate">{example.text}</span>
                  <ChevronRight className="size-3.5 shrink-0 text-muted-foreground" />
                </button>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
