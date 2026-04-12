"use client";

import { Sparkles } from "lucide-react";

const EXAMPLES = [
  "Summarize what this collection is about.",
  "What are the three most important concepts?",
  "Find references to a specific term.",
  "Compare two ideas mentioned in the docs.",
];

interface Props {
  onSelect: (text: string) => void;
  disabled?: boolean;
}

export const EmptyPrompts = ({ onSelect, disabled }: Props) => (
  <div className="flex flex-1 items-center justify-center px-6 py-8">
    <div className="mx-auto w-full max-w-2xl text-center">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-full bg-muted text-muted-foreground">
        <Sparkles className="size-5" />
      </div>
      <h2 className="text-base font-medium">Ask a question, get an answer</h2>
      <p className="mt-1 text-sm text-muted-foreground">
        We'll retrieve the most relevant chunks from your collection and hand them to OpenAI to
        draft a grounded answer.
      </p>
      <div className="mt-6 grid gap-2 sm:grid-cols-2">
        {EXAMPLES.map((text) => (
          <button
            disabled={disabled}
            key={text}
            onClick={() => onSelect(text)}
            type="button"
            className="rounded-lg border border-border bg-card px-4 py-3 text-left text-sm text-foreground transition-colors hover:border-primary hover:bg-accent disabled:cursor-not-allowed disabled:opacity-50"
          >
            {text}
          </button>
        ))}
      </div>
    </div>
  </div>
);
