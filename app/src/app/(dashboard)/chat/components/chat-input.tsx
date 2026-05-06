"use client";

import { Popover } from "@base-ui/react/popover";
import {
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  KeyRound,
  Plus,
  SlidersHorizontal,
  Sparkles,
  Square,
  Thermometer,
} from "lucide-react";
import {
  type KeyboardEvent,
  type ReactElement,
  type ReactNode,
  useCallback,
  useEffect,
  useRef,
  useState,
} from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Collection } from "@/types/bigrag";

const OPENAI_MODELS = [
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
  { value: "gpt-4.1", label: "GPT-4.1" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 turbo" },
];

export type ChatState = {
  hasOpenAIKey: boolean;
  model: string;
  topK: number;
  temperature: number;
  searchMode: "semantic" | "keyword" | "hybrid";
  rerank: boolean;
  systemPrompt: string;
};

type ChatPatch = Partial<ChatState> & { openaiKey?: string };

type PopoverName = "model" | "collection" | "settings" | "key" | null;

interface Props {
  state: ChatState;
  onPatch: (patch: ChatPatch) => void;
  saving: boolean;
  collections: Collection[];
  collection: string;
  onCollectionChange: (name: string) => void;
  isStreaming: boolean;
  onSend: (text: string) => void;
  onStop: () => void;
  disabled: boolean;
}

export const ChatInput = ({
  state,
  onPatch,
  saving,
  collections,
  collection,
  onCollectionChange,
  isStreaming,
  onSend,
  onStop,
  disabled,
}: Props) => {
  const [value, setValue] = useState("");
  const [open, setOpen] = useState<PopoverName>(null);
  const [keyDraft, setKeyDraft] = useState("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!state.hasOpenAIKey) setKeyDraft("");
  }, [state.hasOpenAIKey]);

  const toggle = (p: PopoverName) => setOpen((cur) => (cur === p ? null : p));

  const adjustHeight = useCallback(() => {
    const el = textareaRef.current;
    if (!el) return;
    el.style.height = "auto";
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
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

  return (
    <div className="px-4 pt-2 pb-5 md:px-6">
      <div className="mx-auto max-w-3xl rounded-3xl border border-border bg-background focus-within:border-neutral-200">
        <textarea
          ref={textareaRef}
          aria-label="Message input"
          className="min-h-16 w-full resize-none bg-transparent px-5 pt-5 pb-2 text-base leading-6 placeholder:text-neutral-300 focus-visible:outline-none md:min-h-20 md:pb-3"
          disabled={isStreaming}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder={
            keyIsSet
              ? collection
                ? "Ask bigRAG a followup..."
                : "Pick a collection below to start"
              : "Add your OpenAI API key to start"
          }
          rows={1}
          style={{ maxHeight: 200 }}
          value={value}
        />

        <div className="flex items-end justify-between gap-2 px-3 pb-3 md:px-4 md:pb-4">
          <div className="flex min-w-0 flex-nowrap items-center gap-1 overflow-x-auto">
            <button
              type="button"
              aria-label="Input options"
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => toggle(keyIsSet ? "collection" : "key")}
            >
              <Plus className="size-4" />
            </button>
            <ToolbarPopover
              align="start"
              open={open === "key"}
              onOpenChange={(nextOpen) => setOpen(nextOpen ? "key" : null)}
              trigger={
                <Button
                  className={cn(
                    "h-8 px-3 text-xs",
                    open === "key" && "bg-accent text-accent-foreground",
                    !keyIsSet && "text-destructive",
                  )}
                  variant="ghost"
                >
                  <KeyRound className="size-3" />
                  {keyIsSet ? "OpenAI key saved" : "Add OpenAI key"}
                </Button>
              }
            >
              <div className="w-80 space-y-3 p-3">
                <div>
                  <div className="text-xs font-semibold">OpenAI API key</div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    Saved on the backend and used there for chat responses.
                  </p>
                </div>
                <input
                  aria-label="OpenAI API key"
                  autoComplete="off"
                  className="h-10 w-full rounded-full border border-input bg-background px-4 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  onChange={(e) => setKeyDraft(e.target.value)}
                  placeholder={keyIsSet ? "Paste a replacement key" : "sk-..."}
                  type="password"
                  value={keyDraft}
                />
                <div className="flex items-center justify-between gap-1.5">
                  <span className="text-xs text-muted-foreground">
                    {saving ? "Saving…" : keyIsSet ? "Saved" : ""}
                  </span>
                  <div className="flex gap-1.5">
                    {keyIsSet && (
                      <Button
                        size="sm"
                        variant="ghost"
                        onClick={() => {
                          onPatch({ openaiKey: "" });
                          setKeyDraft("");
                        }}
                      >
                        Clear
                      </Button>
                    )}
                    <Button
                      size="sm"
                      disabled={!keyDraft.trim()}
                      onClick={() => {
                        onPatch({ openaiKey: keyDraft.trim() });
                        setKeyDraft("");
                        setOpen(null);
                      }}
                    >
                      Save
                    </Button>
                  </div>
                </div>
              </div>
            </ToolbarPopover>

            <ModelMenu
              selectedLabel={selectedModelLabel}
              value={state.model}
              onChange={(v) => {
                onPatch({ model: v });
                setOpen(null);
              }}
              open={open === "model"}
              onToggle={() => toggle("model")}
              onClose={() => setOpen(null)}
            />

            <CollectionMenu
              collections={collections}
              value={collection}
              onChange={(name) => {
                onCollectionChange(name);
                setOpen(null);
              }}
              open={open === "collection"}
              onToggle={() => toggle("collection")}
              onClose={() => setOpen(null)}
            />

            <ToolbarPopover
              align="start"
              open={open === "settings"}
              onOpenChange={(nextOpen) => setOpen(nextOpen ? "settings" : null)}
              trigger={
                <Button className="h-8 px-3 text-xs" variant="ghost">
                  <Thermometer className="size-3" />
                  {state.temperature.toFixed(1)}
                  <span className="mx-1 opacity-50">·</span>
                  top-{state.topK}
                </Button>
              }
            >
              <div className="w-72 space-y-4 p-4">
                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">Temperature</span>
                    <span className="font-mono text-xs text-muted-foreground">
                      {state.temperature.toFixed(1)}
                    </span>
                  </div>
                  <input
                    aria-label="Temperature"
                    className="w-full accent-primary"
                    max="1"
                    min="0"
                    step="0.1"
                    type="range"
                    value={state.temperature}
                    onChange={(e) => onPatch({ temperature: Number.parseFloat(e.target.value) })}
                  />
                </div>

                <div className="space-y-1.5">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-semibold">Top K chunks</span>
                    <span className="font-mono text-xs text-muted-foreground">{state.topK}</span>
                  </div>
                  <input
                    aria-label="Top K"
                    className="w-full accent-primary"
                    max="20"
                    min="1"
                    step="1"
                    type="range"
                    value={state.topK}
                    onChange={(e) => onPatch({ topK: Number.parseInt(e.target.value, 10) })}
                  />
                </div>

                <div className="space-y-1.5">
                  <span className="text-xs font-semibold">Search mode</span>
                  <div className="grid grid-cols-3 gap-1 rounded-full border border-border p-1">
                    {(["semantic", "keyword", "hybrid"] as const).map((mode) => (
                      <button
                        key={mode}
                        type="button"
                        className={cn(
                          "h-7 rounded-full px-2 text-xs font-medium capitalize hover:bg-accent",
                          state.searchMode === mode && "bg-foreground text-background",
                        )}
                        onClick={() => onPatch({ searchMode: mode })}
                      >
                        {mode}
                      </button>
                    ))}
                  </div>
                </div>

                <label className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border px-3 py-2">
                  <span className="text-xs font-semibold">Use reranker when configured</span>
                  <input
                    aria-label="Use reranker when configured"
                    className="accent-primary"
                    checked={state.rerank}
                    type="checkbox"
                    onChange={(e) => onPatch({ rerank: e.target.checked })}
                  />
                </label>

                <div className="space-y-1.5">
                  <span className="text-xs font-semibold">System prompt</span>
                  <textarea
                    aria-label="System prompt"
                    className="w-full rounded-2xl border border-input bg-background px-3 py-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                    onChange={(e) => onPatch({ systemPrompt: e.target.value })}
                    rows={4}
                    value={state.systemPrompt}
                  />
                </div>
                {saving && <div className="text-xs text-muted-foreground">Saving…</div>}
              </div>
            </ToolbarPopover>
          </div>

          {isStreaming ? (
            <Button
              aria-label="Stop"
              className="size-9 shrink-0 p-0"
              onClick={onStop}
              variant="ghost"
            >
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              aria-label="Send message"
              className="size-9 shrink-0 bg-neutral-400 p-0 text-white hover:bg-neutral-500 disabled:bg-neutral-300"
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

const ModelMenu = ({
  selectedLabel,
  value,
  onChange,
  open,
  onToggle,
  onClose,
}: {
  selectedLabel: string;
  value: string;
  onChange: (v: string) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}) => (
  <ToolbarPopover
    align="end"
    open={open}
    onOpenChange={(nextOpen) => (nextOpen ? onToggle() : onClose())}
    trigger={
      <Button className="h-8 px-3 text-xs font-semibold" variant="ghost">
        <Sparkles className="size-3.5 text-warning" />
        {selectedLabel}
        <ChevronDown className="size-3" />
      </Button>
    }
  >
    <div className="w-72 p-1.5">
      {OPENAI_MODELS.map((m) => (
        <button
          type="button"
          key={m.value}
          onClick={() => onChange(m.value)}
          className={cn(
            "flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left text-sm hover:bg-accent",
            m.value === value && "bg-accent font-semibold text-foreground",
          )}
        >
          <Sparkles className="size-4 shrink-0 text-warning" />
          <span className="flex-1 truncate">{m.label}</span>
          {m.value === value && <Check className="size-4" />}
        </button>
      ))}
      <div className="my-1 h-px bg-border" />
      <button
        type="button"
        className="flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left text-sm hover:bg-accent"
      >
        <SlidersHorizontal className="size-4 shrink-0 text-muted-foreground" />
        <span className="flex-1 truncate">Configure</span>
      </button>
    </div>
  </ToolbarPopover>
);

const CollectionMenu = ({
  collections,
  value,
  onChange,
  open,
  onToggle,
  onClose,
}: {
  collections: Collection[];
  value: string;
  onChange: (v: string) => void;
  open: boolean;
  onToggle: () => void;
  onClose: () => void;
}) => (
  <ToolbarPopover
    align="start"
    open={open}
    onOpenChange={(nextOpen) => (nextOpen ? onToggle() : onClose())}
    trigger={
      <Button
        className={cn("h-8 px-3 text-xs font-semibold", !value && "text-destructive")}
        variant="ghost"
      >
        <BookOpen className="size-3.5" />
        {value || "Choose collection"}
        <ChevronDown className="size-3" />
      </Button>
    }
  >
    <div className="max-h-64 w-64 overflow-y-auto p-1.5">
      {collections.length === 0 && (
        <p className="px-3 py-2 text-xs text-muted-foreground">No collections yet</p>
      )}
      {collections.map((c) => (
        <button
          type="button"
          key={c.id}
          onClick={() => onChange(c.name)}
          className={cn(
            "flex h-10 w-full items-center gap-2 rounded-2xl px-3 text-left text-xs hover:bg-accent",
            c.name === value && "bg-accent font-semibold text-foreground",
          )}
        >
          <span className="flex-1 truncate">{c.name}</span>
          <span className="font-mono text-xs text-muted-foreground">{c.document_count}</span>
          {c.name === value && <Check className="size-3.5" />}
        </button>
      ))}
    </div>
  </ToolbarPopover>
);

const ToolbarPopover = ({
  align = "start",
  children,
  open,
  onOpenChange,
  trigger,
}: {
  align?: "start" | "end";
  children: ReactNode;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  trigger: ReactElement;
}) => (
  <Popover.Root open={open} onOpenChange={onOpenChange}>
    <Popover.Trigger render={trigger} />
    <Popover.Portal>
      <Popover.Positioner align={align} className="z-50" side="top" sideOffset={8}>
        <Popover.Popup className="rounded-3xl border border-border bg-popover outline-none">
          {children}
        </Popover.Popup>
      </Popover.Positioner>
    </Popover.Portal>
  </Popover.Root>
);
