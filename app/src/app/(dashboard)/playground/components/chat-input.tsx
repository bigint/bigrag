"use client";

import { ArrowUp, ChevronDown, KeyRound, type Settings2, Square, Thermometer } from "lucide-react";
import { type KeyboardEvent, useCallback, useEffect, useRef, useState } from "react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { Collection } from "@/types/bigrag";

export const OPENAI_MODELS = [
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
    <div className="px-4 py-3 md:px-6">
      <div className="mx-auto max-w-3xl rounded-xl border border-border bg-muted/30 shadow-sm transition-colors focus-within:border-ring focus-within:bg-background">
        <textarea
          ref={textareaRef}
          aria-label="Message input"
          className="w-full resize-none bg-transparent px-4 pt-3 pb-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none"
          disabled={isStreaming}
          onChange={(e) => {
            setValue(e.target.value);
            adjustHeight();
          }}
          onKeyDown={handleKeyDown}
          placeholder={
            keyIsSet
              ? collection
                ? "Ask a question of your collection…"
                : "Pick a collection below to start"
              : "Add your OpenAI API key to start"
          }
          rows={1}
          style={{ maxHeight: 200 }}
          value={value}
        />

        <div className="flex items-center justify-between gap-1 px-3 pb-2">
          <div className="flex flex-wrap items-center gap-0.5">
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
                      <div className="text-xs font-medium">OpenAI API key</div>
                      <p className="mt-0.5 text-[11px] text-muted-foreground">
                        Saved on the server so it follows you across devices. Only used to call
                        api.openai.com from your browser.
                      </p>
                    </div>
                    <input
                      aria-label="OpenAI API key"
                      autoComplete="off"
                      className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      onChange={(e) => setKeyDraft(e.target.value)}
                      placeholder="sk-..."
                      type="password"
                      value={keyDraft}
                    />
                    <div className="flex items-center justify-between gap-1.5">
                      <span className="text-[11px] text-muted-foreground">
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

            <Sep />

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

            <Sep />

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

            <Sep />

            <div className="relative">
              <Button
                className="h-auto px-2 py-1 text-[11px]"
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
                  <div className="w-64 space-y-3 p-3">
                    <div className="space-y-1.5">
                      <div className="flex items-center justify-between">
                        <span className="text-xs font-medium">Temperature</span>
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
                        <span className="text-xs font-medium">Top K chunks</span>
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
                      <span className="text-xs font-medium">System prompt</span>
                      <textarea
                        aria-label="System prompt"
                        className="w-full rounded-md border border-input bg-background px-3 py-2 text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                        onChange={(e) => onPatch({ systemPrompt: e.target.value })}
                        rows={4}
                        value={state.systemPrompt}
                      />
                    </div>
                    {saving && <div className="text-[11px] text-muted-foreground">Saving…</div>}
                  </div>
                </Dropdown>
              )}
            </div>
          </div>

          {isStreaming ? (
            <Button aria-label="Stop" className="rounded-lg p-2" onClick={onStop} variant="ghost">
              <Square className="size-4" />
            </Button>
          ) : (
            <Button
              aria-label="Send message"
              className="rounded-lg p-2"
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

const Sep = () => <span className="mx-0.5 text-border">|</span>;

const PopoverButton = ({
  icon: Icon,
  label,
  onClick,
  active,
  missing,
}: {
  icon: typeof Settings2;
  label: string;
  onClick: () => void;
  active: boolean;
  missing?: boolean;
}) => (
  <Button
    className={cn(
      "h-auto px-2 py-1 text-[11px]",
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
    <Button className="h-auto px-2 py-1 text-[11px] font-medium" onClick={onToggle} variant="ghost">
      {selectedLabel}
      <ChevronDown className="size-3" />
    </Button>
    {open && (
      <Dropdown onClose={onClose}>
        <div className="w-52 py-1">
          {OPENAI_MODELS.map((m) => (
            <button
              type="button"
              key={m.value}
              onClick={() => onChange(m.value)}
              className={cn(
                "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent",
                m.value === value && "font-medium text-foreground",
              )}
            >
              <span className="flex-1 truncate">{m.label}</span>
              <span className="font-mono text-[10px] text-muted-foreground">{m.value}</span>
            </button>
          ))}
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
      className={cn("h-auto px-2 py-1 text-[11px] font-medium", !value && "text-destructive")}
      onClick={onToggle}
      variant="ghost"
    >
      {value || "Pick collection"}
      <ChevronDown className="size-3" />
    </Button>
    {open && (
      <Dropdown onClose={onClose}>
        <div className="max-h-60 w-56 overflow-y-auto py-1">
          {collections.length === 0 && (
            <p className="px-3 py-2 text-xs text-muted-foreground">No collections yet</p>
          )}
          {collections.map((c) => (
            <button
              type="button"
              key={c.id}
              onClick={() => onChange(c.name)}
              className={cn(
                "flex w-full items-center gap-2 px-3 py-1.5 text-left text-xs hover:bg-accent",
                c.name === value && "font-medium text-foreground",
              )}
            >
              <span className="flex-1 truncate">{c.name}</span>
              <span className="font-mono text-[10px] text-muted-foreground">
                {c.document_count}
              </span>
            </button>
          ))}
        </div>
      </Dropdown>
    )}
  </div>
);

const Dropdown = ({ children, onClose }: { children: React.ReactNode; onClose: () => void }) => (
  <>
    <div aria-hidden="true" className="fixed inset-0 z-40" onClick={onClose} />
    <div className="absolute bottom-full left-0 z-50 mb-1 rounded-lg border border-border bg-popover shadow-md">
      {children}
    </div>
  </>
);
