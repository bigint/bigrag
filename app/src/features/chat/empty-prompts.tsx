import type { LucideIcon } from "lucide-react";
import {
  BookOpen,
  Braces,
  FileSearch,
  Layers3,
  MessageCircle,
  Search,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

const PROMPT_GROUPS: {
  title: string;
  icon: LucideIcon;
  prompts: { icon: LucideIcon; text: string }[];
}[] = [
  {
    title: "Understand",
    icon: FileSearch,
    prompts: [
      { icon: MessageCircle, text: "Summarize what this collection is about." },
      { icon: Layers3, text: "What are the three most important concepts?" },
    ],
  },
  {
    title: "Verify",
    icon: ShieldCheck,
    prompts: [
      { icon: Search, text: "Find references to a specific term." },
      { icon: BookOpen, text: "Which source should I read first?" },
    ],
  },
  {
    title: "Compare",
    icon: Braces,
    prompts: [
      { icon: FileSearch, text: "Compare two ideas mentioned in the docs." },
      { icon: ShieldCheck, text: "List the facts that need citations." },
    ],
  },
];

interface Props {
  collection: string;
  collectionCount: number;
  disabled?: boolean;
  hasOpenAIKey: boolean;
  onSelect: (text: string) => void;
}

export const EmptyPrompts = ({
  collection,
  collectionCount,
  disabled,
  hasOpenAIKey,
  onSelect,
}: Props) => {
  const missingCollection = collectionCount === 0 || !collection;
  const notice = hasOpenAIKey
    ? missingCollection
      ? "Choose a collection to start asking questions."
      : null
    : "Add an API key to start asking questions.";

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-8 md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-6">
        <section className="mx-auto max-w-2xl text-center">
          <h1 className="text-balance text-3xl font-semibold leading-tight tracking-normal md:text-4xl">
            Ask your collection.
          </h1>
          <p className="mt-3 text-sm leading-6 text-muted-foreground">
            Get a concise answer with source citations, then open the evidence when you need to
            audit the result.
          </p>
          {notice && (
            <div className="mx-auto mt-4 inline-flex max-w-full items-center gap-2 rounded-md border border-border bg-muted/60 px-3 py-2 text-xs font-semibold text-muted-foreground">
              <TriangleAlert className="size-3.5 shrink-0" />
              <span className="truncate">{notice}</span>
            </div>
          )}
        </section>

        <section className="grid gap-3 md:grid-cols-3">
          {PROMPT_GROUPS.map((group) => {
            const GroupIcon = group.icon;
            return (
              <div
                key={group.title}
                className="overflow-hidden rounded-xl border border-border bg-background"
              >
                <div className="flex items-center gap-2 border-b border-border px-4 py-3">
                  <GroupIcon className="size-4 text-muted-foreground" />
                  <h2 className="text-sm font-semibold">{group.title}</h2>
                </div>
                <div className="divide-y divide-border">
                  {group.prompts.map((prompt) => {
                    const PromptIcon = prompt.icon;
                    return (
                      <button
                        disabled={disabled}
                        key={prompt.text}
                        onClick={() => onSelect(prompt.text)}
                        type="button"
                        className="flex min-h-16 w-full items-center gap-3 px-4 py-3 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
                      >
                        <span className="flex size-8 shrink-0 items-center justify-center rounded-xl border border-border bg-muted">
                          <PromptIcon className="size-4 text-muted-foreground" />
                        </span>
                        <span className="text-sm font-semibold leading-5">{prompt.text}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            );
          })}
        </section>
      </div>
    </div>
  );
};
