"use client";

import {
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  KeyRound,
  type LucideIcon,
  Plus,
  SlidersHorizontal,
  Sparkles,
  Square,
  Thermometer,
} from "lucide-react";
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
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

export type PlaygroundState = {
  openaiKey: string;
  model: string;
  topK: number;
  temperature: number;
  systemPrompt: string;
};

type PopoverName = "model" | "collection" | "settings" | "key" | null;

interface Props {
  state: PlaygroundState;
  onPatch: (patch: Partial<PlaygroundState>) => void;
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
  const [keyDraft, setKeyDraft] = useState(state.openaiKey);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => setKeyDraft(state.openaiKey), [state.openaiKey]);

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
  const keyIsSet = state.openaiKey.length > 8;

  return (
    <div className="px-4 pt-2 pb-5 md:px-6">
      <div className="mx-auto max-w-3xl rounded-3xl border border-border bg-background transition-all duration-300 ease-out focus-within:border-neutral-200">
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
              className="flex size-8 shrink-0 items-center justify-center rounded-full text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              onClick={() => toggle(keyIsSet ? "collection" : "key")}
            >
              <Plus className="size-4" />
            </button>
            <div className="relative">
              <PopoverButton
                icon={KeyRound}
                label={keyIsSet ? `OpenAI key …${state.openaiKey.slice(-4)}` : "Add OpenAI key"}
                active={open === "key"}
                missing={!keyIsSet}
                onClick={() => toggle("key")}
              />
              {open === "key" && (
                <Dropdown onClose={() => setOpen(null)}>
                  <div className="w-80 space-y-3 p-3">
                    <div>
                      <div className="text-xs font-semibold">OpenAI API key</div>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        Saved on the server so it follows you across devices. Only used to call
                        api.openai.com from your browser.
                      </p>
                    </div>
                    <input
                      aria-label="OpenAI API key"
                      autoComplete="off"
                      className="h-10 w-full rounded-full border border-input bg-background px-4 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onChange={(e) => setKeyDraft(e.target.value)}
                      placeholder="sk-..."
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
                          disabled={!keyDraft.trim() || keyDraft === state.openaiKey}
                          onClick={() => {
                            onPatch({ openaiKey: keyDraft.trim() });
                            setOpen(null);
                          }}
                        >
                          Save
                        </Button>
                      </div>
                    </div>
                  </div>
                </Dropdown>
              )}
            </div>

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

            <div className="relative">
              <Button
                className="h-8 px-3 text-xs"
                onClick={() => toggle("settings")}
                variant="ghost"
              >
                <Thermometer className="size-3" />
                {state.temperature.toFixed(1)}
                <span className="mx-1 opacity-50">·</span>
                top-{state.topK}
              </Button>
              {open === "settings" && (
                <Dropdown onClose={() => setOpen(null)}>
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
                        onChange={(e) =>
                          onPatch({ temperature: Number.parseFloat(e.target.value) })
                        }
                      />
                    </div>

                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-semibold">Top K chunks</span>
                        <span className="font-mono text-xs text-muted-foreground">
                          {state.topK}
                        </span>
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
                </Dropdown>
              )}
            </div>
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

const PopoverButton = ({
  icon: Icon,
  label,
  onClick,
  active,
  missing,
}: {
  icon: LucideIcon;
  label: string;
  onClick: () => void;
  active: boolean;
  missing?: boolean;
}) => (
  <Button
    className={cn(
      "h-8 px-3 text-xs",
      active && "bg-accent text-accent-foreground",
      missing && "text-destructive",
    )}
    onClick={onClick}
    variant="ghost"
  >
    <Icon className="size-3" />
    {label}
  </Button>
);

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
  <div className="relative">
    <Button className="h-8 px-3 text-xs font-semibold" onClick={onToggle} variant="ghost">
      <Sparkles className="size-3.5 text-warning" />
      {selectedLabel}
      <ChevronDown className="size-3" />
    </Button>
    {open && (
      <Dropdown align="right" onClose={onClose}>
        <div className="w-72 p-1.5">
          {OPENAI_MODELS.map((m) => (
            <button
              type="button"
              key={m.value}
              onClick={() => onChange(m.value)}
              className={cn(
                "flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left text-sm transition-colors hover:bg-accent",
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
            className="flex h-11 w-full items-center gap-3 rounded-2xl px-3 text-left text-sm transition-colors hover:bg-accent"
          >
            <SlidersHorizontal className="size-4 shrink-0 text-muted-foreground" />
            <span className="flex-1 truncate">Configure</span>
          </button>
        </div>
      </Dropdown>
    )}
  </div>
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
  <div className="relative">
    <Button
      className={cn("h-8 px-3 text-xs font-semibold", !value && "text-destructive")}
      onClick={onToggle}
      variant="ghost"
    >
      <BookOpen className="size-3.5" />
      {value || "Choose collection"}
      <ChevronDown className="size-3" />
    </Button>
    {open && (
      <Dropdown onClose={onClose}>
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
                "flex h-10 w-full items-center gap-2 rounded-2xl px-3 text-left text-xs transition-colors hover:bg-accent",
                c.name === value && "bg-accent font-semibold text-foreground",
              )}
            >
              <span className="flex-1 truncate">{c.name}</span>
              <span className="font-mono text-xs text-muted-foreground">{c.document_count}</span>
              {c.name === value && <Check className="size-3.5" />}
            </button>
          ))}
        </div>
      </Dropdown>
    )}
  </div>
);

const Dropdown = ({
  align = "left",
  children,
  onClose,
}: {
  align?: "left" | "right";
  children: React.ReactNode;
  onClose: () => void;
}) => (
  <>
    <div aria-hidden="true" className="fixed inset-0 z-40" onClick={onClose} />
    <div
      className={cn(
        "absolute bottom-full z-50 mb-2 rounded-3xl border border-border bg-popover",
        align === "right" ? "right-0" : "left-0",
      )}
    >
      {children}
    </div>
  </>
);
