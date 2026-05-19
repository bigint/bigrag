import { Button, cn, Textarea } from "@atelier/ui";
import {
  ArrowUp,
  BookOpen,
  ChevronDown,
  KeyRound,
  SlidersHorizontal,
  Sparkles,
  Square,
} from "lucide-react";
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import type { Collection } from "@/types/bigrag";
import {
  type ChatPatch,
  type ChatState,
  CollectionMenu,
  KeyMenu,
  ModelMenu,
  OPENAI_MODELS,
  SettingsMenu,
  ToolbarPopover,
} from "./chat-input-controls";

export type { ChatState } from "./chat-input-controls";

type PopoverName = "model" | "collection" | "settings" | "key" | null;

interface Props {
  collection: string;
  collections: Collection[];
  disabled: boolean;
  isStreaming: boolean;
  onCollectionChange: (name: string) => void;
  onPatch: (patch: ChatPatch) => void;
  onSend: (text: string) => void;
  onStop: () => void;
  saving: boolean;
  state: ChatState;
}

export const ChatInput = ({
  collection,
  collections,
  disabled,
  isStreaming,
  onCollectionChange,
  onPatch,
  onSend,
  onStop,
  saving,
  state,
}: Props) => {
  const [value, setValue] = useState("");
  const [open, setOpen] = useState<PopoverName>(null);
  const [keyDraft, setKeyDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useClearKeyDraft(state.hasOpenAIKey, setKeyDraft);

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 184)}px`;
  }, []);

  const handleSend = () => {
    if (!value.trim() || disabled) return;
    onSend(value.trim());
    setValue("");
    if (textareaRef.current) textareaRef.current.style.height = "auto";
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const selectedModelLabel =
    OPENAI_MODELS.find((m) => m.value === state.model)?.label ?? state.model;
  const keyIsSet = state.hasOpenAIKey;
  const readyLabel = keyIsSet ? "API key saved" : "Add API key";

  return (
    <div className="shrink-0 border-t border-border bg-background px-3 py-3 md:px-5">
      <div className="mx-auto w-full max-w-4xl rounded-xl border border-border bg-card p-2">
        <div className="flex flex-col gap-2 px-1 pb-2 md:flex-row md:items-center md:justify-between">
          <div className="flex min-w-0 flex-wrap items-center gap-1.5">
            <ToolbarPopover
              align="start"
              open={open === "collection"}
              onOpenChange={(nextOpen) => setOpen(nextOpen ? "collection" : null)}
              trigger={
                <Button
                  className={cn("h-8 max-w-full px-2.5 text-xs", !collection && "text-destructive")}
                  variant="ghost"
                >
                  <BookOpen className="size-3.5" />
                  <span className="truncate">{collection || "Choose collection"}</span>
                  <ChevronDown className="size-3" />
                </Button>
              }
            >
              <CollectionMenu
                collections={collections}
                onChange={(name) => {
                  onCollectionChange(name);
                  setOpen(null);
                }}
                value={collection}
              />
            </ToolbarPopover>

            <ToolbarPopover
              align="start"
              open={open === "model"}
              onOpenChange={(nextOpen) => setOpen(nextOpen ? "model" : null)}
              trigger={
                <Button className="h-8 px-2.5 text-xs" variant="ghost">
                  <Sparkles className="size-3.5 text-warning" />
                  <span className="truncate">{selectedModelLabel}</span>
                  <ChevronDown className="size-3" />
                </Button>
              }
            >
              <ModelMenu
                onChange={(model) => {
                  onPatch({ model });
                  setOpen(null);
                }}
                value={state.model}
              />
            </ToolbarPopover>

            <ToolbarPopover
              align="start"
              open={open === "settings"}
              onOpenChange={(nextOpen) => setOpen(nextOpen ? "settings" : null)}
              trigger={
                <Button className="h-8 px-2.5 text-xs" variant="ghost">
                  <SlidersHorizontal className="size-3.5" />
                  Search
                </Button>
              }
            >
              <SettingsMenu onPatch={onPatch} saving={saving} state={state} />
            </ToolbarPopover>
          </div>

          <ToolbarPopover
            align="end"
            open={open === "key"}
            onOpenChange={(nextOpen) => setOpen(nextOpen ? "key" : null)}
            trigger={
              <Button
                className={cn("h-8 justify-start px-2.5 text-xs", !keyIsSet && "text-destructive")}
                variant="ghost"
              >
                <KeyRound className="size-3.5" />
                {readyLabel}
              </Button>
            }
          >
            <KeyMenu
              keyDraft={keyDraft}
              keyIsSet={keyIsSet}
              onClear={() => {
                onPatch({ openaiKey: "" });
                setKeyDraft("");
              }}
              onSave={() => {
                onPatch({ openaiKey: keyDraft.trim() });
                setKeyDraft("");
                setOpen(null);
              }}
              saving={saving}
              setKeyDraft={setKeyDraft}
            />
          </ToolbarPopover>
        </div>

        <div className="flex items-end gap-2 rounded-lg border border-border bg-background px-3 py-2">
          <Textarea
            ref={textareaRef}
            aria-label="Message input"
            className="min-h-12 resize-none rounded-none border-0 bg-transparent px-0 py-2 text-base leading-6 placeholder:text-muted-foreground/65 focus-visible:ring-0"
            containerClassName="flex-1"
            disabled={isStreaming}
            onChange={(e) => {
              setValue(e.target.value);
              adjustHeight();
            }}
            onKeyDown={handleKeyDown}
            placeholder={
              keyIsSet
                ? collection
                  ? "Ask a grounded question..."
                  : "Choose a collection before starting."
                : "Save an OpenAI API key before starting."
            }
            rows={1}
            style={{ maxHeight: 184 }}
            value={value}
          />

          {isStreaming ? (
            <Button aria-label="Stop response" className="size-10 shrink-0 p-0" onClick={onStop}>
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              aria-label="Send message"
              className="size-10 shrink-0 p-0"
              disabled={disabled || !value.trim()}
              onClick={handleSend}
            >
              <ArrowUp className="size-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

const useClearKeyDraft = (hasOpenAIKey: boolean, setKeyDraft: (value: string) => void) => {
  useEffect(() => {
    if (!hasOpenAIKey) setKeyDraft("");
  }, [hasOpenAIKey, setKeyDraft]);
};
