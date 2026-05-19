import { Button } from "@atelier/ui";
import { ArrowUpRight, RefreshCcw, Shuffle, TriangleAlert } from "lucide-react";

interface Props {
  collection: string;
  collectionCount: number;
  disabled?: boolean;
  hasOpenAIKey: boolean;
  isGeneratingQuestions: boolean;
  onGenerateQuestions: () => void;
  onSelect: (text: string) => void;
  questions: readonly string[];
}

export const EmptyPrompts = ({
  collection,
  collectionCount,
  disabled,
  hasOpenAIKey,
  isGeneratingQuestions,
  onGenerateQuestions,
  onSelect,
  questions,
}: Props) => {
  const missingCollection = collectionCount === 0 || !collection;
  const notice = hasOpenAIKey
    ? missingCollection
      ? "Choose a collection to start asking questions."
      : null
    : "Add an API key to start asking questions.";
  const canGenerateQuestions = !disabled && !missingCollection && !isGeneratingQuestions;
  const hasQuestions = questions.length > 0;

  return (
    <div className="min-h-0 flex-1 overflow-y-auto px-4 py-6 md:px-6 lg:px-8">
      <div className="mx-auto flex w-full max-w-4xl flex-col gap-5">
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

        <section className="mx-auto w-full max-w-3xl overflow-hidden rounded-xl border border-border bg-background">
          <div className="flex items-center justify-between gap-3 border-b border-border px-4 py-2.5">
            <div className="min-w-0">
              <div className="text-[11px] font-semibold uppercase tracking-normal text-muted-foreground">
                {collection || "Collection"}
              </div>
              <h2 className="truncate text-[13px] font-semibold leading-5">Question starters</h2>
            </div>
            {hasQuestions && (
              <Button
                aria-label="Refresh questions"
                className="h-7 px-2.5"
                disabled={!canGenerateQuestions}
                onClick={onGenerateQuestions}
                size="sm"
                variant="outline"
              >
                <RefreshCcw
                  className={isGeneratingQuestions ? "size-3.5 animate-spin" : "size-3.5"}
                />
                Refresh
              </Button>
            )}
          </div>

          {hasQuestions ? (
            <div className="divide-y divide-border">
              {questions.map((question, index) => (
                <button
                  className="group flex min-h-[3.25rem] w-full items-center gap-2.5 px-4 py-2.5 text-left hover:bg-muted disabled:cursor-not-allowed disabled:opacity-45"
                  disabled={disabled}
                  key={question}
                  onClick={() => onSelect(question)}
                  type="button"
                >
                  <span className="flex size-7 shrink-0 items-center justify-center rounded-lg border border-border bg-muted text-xs font-semibold text-muted-foreground">
                    {index + 1}
                  </span>
                  <span className="min-w-0 flex-1 text-sm font-semibold leading-5">{question}</span>
                  <ArrowUpRight className="size-3.5 shrink-0 text-muted-foreground opacity-0 group-hover:opacity-100" />
                </button>
              ))}
            </div>
          ) : (
            <div className="flex min-h-48 flex-col items-center justify-center gap-3 px-6 py-10 text-center">
              <Button
                disabled={!canGenerateQuestions}
                onClick={onGenerateQuestions}
                size="lg"
                variant="primary"
              >
                <Shuffle className="size-4" />
                {isGeneratingQuestions ? "Generating" : "Generate 5 questions"}
              </Button>
              <p className="max-w-sm text-sm leading-6 text-muted-foreground">
                Uses your saved AI key to create questions from ready documents in this collection.
              </p>
            </div>
          )}
        </section>
      </div>
    </div>
  );
};
