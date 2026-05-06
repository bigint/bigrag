"use client";

import {
  BookOpen,
  ChevronRight,
  Cpu,
  Database,
  FileSearch,
  MessageCircle,
  Plug,
} from "lucide-react";
import { Logo } from "@/components/brand/logo";

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
  return (
    <div className="flex min-h-0 flex-1 items-start justify-center overflow-y-auto px-4 pt-24 pb-8 text-center md:pt-32">
      <div className="mx-auto w-full max-w-2xl">
        <Logo className="mx-auto mb-5 scale-110 justify-center" withWordmark={false} />
        <h2 className="mt-2 text-3xl font-semibold leading-tight tracking-normal">
          Your RAG Worker
        </h2>
        <p className="mx-auto mt-2 max-w-sm text-sm leading-5 text-muted-foreground">
          Ask a collection and get grounded answers with source citations.
        </p>

        <div className="mt-6 w-full overflow-hidden rounded-2xl border border-border bg-background text-left">
          <div className="border-b border-border px-4 py-2.5 text-xs font-semibold text-muted-foreground">
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
                  className="flex min-h-8 w-full items-center gap-2 px-4 py-2 text-left text-xs font-semibold hover:bg-muted disabled:cursor-not-allowed disabled:opacity-50"
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
