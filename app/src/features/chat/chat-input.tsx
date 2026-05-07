import { Popover } from "@base-ui/react/popover";
import {
  ArrowUp,
  BookOpen,
  Check,
  ChevronDown,
  KeyRound,
  SlidersHorizontal,
  Sparkles,
  Square,
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

  useEffect(() => {
    if (!state.hasOpenAIKey) setKeyDraft("");
  }, [state.hasOpenAIKey]);

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
      <div className="mx-auto w-full max-w-5xl overflow-hidden rounded-3xl border border-border bg-card">
        <div className="flex flex-col gap-2 border-b border-border px-3 py-2 md:flex-row md:items-center md:justify-between">
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

        <div className="grid gap-2 p-3">
          <textarea
            ref={textareaRef}
            aria-label="Message input"
            className="min-h-16 w-full resize-none bg-transparent text-base leading-6 placeholder:text-muted-foreground/65 focus-visible:outline-none"
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

          <div className="flex items-center justify-end gap-3 border-t border-border pt-3">
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
    </div>
  );
};

const KeyMenu = ({
  keyDraft,
  keyIsSet,
  onClear,
  onSave,
  saving,
  setKeyDraft,
}: {
  keyDraft: string;
  keyIsSet: boolean;
  onClear: () => void;
  onSave: () => void;
  saving: boolean;
  setKeyDraft: (value: string) => void;
}) => (
  <div className="w-[min(22rem,calc(100vw-2rem))] space-y-3 p-4">
    <div>
      <div className="text-sm font-semibold">OpenAI API key</div>
      <p className="mt-1 text-xs leading-5 text-muted-foreground">
        Stored by the backend and used only for chat generation.
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
    <div className="flex items-center justify-between gap-2">
      <span className="text-xs text-muted-foreground">
        {saving ? "Saving..." : keyIsSet ? "Saved" : "Not saved"}
      </span>
      <div className="flex gap-1.5">
        {keyIsSet && (
          <Button size="sm" variant="ghost" onClick={onClear}>
            Clear
          </Button>
        )}
        <Button size="sm" disabled={!keyDraft.trim()} onClick={onSave}>
          Save
        </Button>
      </div>
    </div>
  </div>
);

const ModelMenu = ({ onChange, value }: { onChange: (v: string) => void; value: string }) => (
  <div className="w-[min(18rem,calc(100vw-2rem))] p-1.5">
    {OPENAI_MODELS.map((model) => (
      <button
        type="button"
        key={model.value}
        onClick={() => onChange(model.value)}
        className={cn(
          "flex h-10 w-full items-center gap-3 rounded-xl px-3 text-left text-sm hover:bg-accent",
          model.value === value && "bg-accent font-semibold text-foreground",
        )}
      >
        <Sparkles className="size-4 shrink-0 text-warning" />
        <span className="flex-1 truncate">{model.label}</span>
        {model.value === value && <Check className="size-4" />}
      </button>
    ))}
  </div>
);

const CollectionMenu = ({
  collections,
  onChange,
  value,
}: {
  collections: Collection[];
  onChange: (v: string) => void;
  value: string;
}) => (
  <div className="max-h-72 w-[min(20rem,calc(100vw-2rem))] overflow-y-auto p-1.5">
    {collections.length === 0 && (
      <p className="px-3 py-2 text-xs text-muted-foreground">No collections yet</p>
    )}
    {collections.map((collection) => (
      <button
        type="button"
        key={collection.id}
        onClick={() => onChange(collection.name)}
        className={cn(
          "flex min-h-11 w-full items-center gap-3 rounded-xl px-3 text-left text-sm hover:bg-accent",
          collection.name === value && "bg-accent font-semibold text-foreground",
        )}
      >
        <span className="min-w-0 flex-1">
          <span className="block truncate">{collection.name}</span>
          <span className="mt-0.5 block truncate text-xs font-normal text-muted-foreground">
            {collection.default_search_mode} / {collection.embedding_model}
          </span>
        </span>
        <span className="font-mono text-xs text-muted-foreground">{collection.document_count}</span>
        {collection.name === value && <Check className="size-3.5" />}
      </button>
    ))}
  </div>
);

const SettingsMenu = ({
  onPatch,
  saving,
  state,
}: {
  onPatch: (patch: ChatPatch) => void;
  saving: boolean;
  state: ChatState;
}) => (
  <div className="w-[min(24rem,calc(100vw-2rem))] space-y-4 p-4">
    <RangeControl
      label="Temperature"
      max={1}
      min={0}
      step={0.1}
      value={state.temperature}
      valueLabel={state.temperature.toFixed(1)}
      onChange={(value) => onPatch({ temperature: value })}
    />
    <RangeControl
      label="Top K chunks"
      max={20}
      min={1}
      step={1}
      value={state.topK}
      valueLabel={String(state.topK)}
      onChange={(value) => onPatch({ topK: Math.round(value) })}
    />

    <div className="space-y-2">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        Search mode
      </span>
      <div className="grid grid-cols-3 overflow-hidden rounded-full border border-border">
        {(["semantic", "keyword", "hybrid"] as const).map((mode) => (
          <button
            key={mode}
            type="button"
            className={cn(
              "h-9 border-r border-border px-2 text-xs font-semibold capitalize last:border-r-0 hover:bg-accent",
              state.searchMode === mode && "bg-foreground text-background hover:bg-foreground",
            )}
            onClick={() => onPatch({ searchMode: mode })}
          >
            {mode}
          </button>
        ))}
      </div>
    </div>

    <label className="flex cursor-pointer items-center justify-between gap-3 rounded-2xl border border-border px-3 py-2.5">
      <span>
        <span className="block text-sm font-semibold">Rerank when configured</span>
        <span className="block text-xs text-muted-foreground">
          Uses the collection reranker if available.
        </span>
      </span>
      <input
        aria-label="Use reranker when configured"
        checked={state.rerank}
        className="size-4 accent-primary"
        type="checkbox"
        onChange={(e) => onPatch({ rerank: e.target.checked })}
      />
    </label>

    <div className="space-y-2">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        System prompt
      </span>
      <textarea
        aria-label="System prompt"
        className="min-h-28 w-full resize-y rounded-2xl border border-input bg-background px-3 py-2 text-xs leading-5 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        onChange={(e) => onPatch({ systemPrompt: e.target.value })}
        value={state.systemPrompt}
      />
    </div>
    {saving && <div className="text-xs text-muted-foreground">Saving...</div>}
  </div>
);

const RangeControl = ({
  label,
  max,
  min,
  onChange,
  step,
  value,
  valueLabel,
}: {
  label: string;
  max: number;
  min: number;
  onChange: (value: number) => void;
  step: number;
  value: number;
  valueLabel: string;
}) => (
  <div className="space-y-2">
    <div className="flex items-center justify-between gap-3">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        {label}
      </span>
      <span className="font-mono text-xs font-semibold">{valueLabel}</span>
    </div>
    <input
      aria-label={label}
      className="w-full accent-primary"
      max={max}
      min={min}
      step={step}
      type="range"
      value={value}
      onChange={(e) => onChange(Number.parseFloat(e.target.value))}
    />
  </div>
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
        <Popover.Popup className="overflow-hidden rounded-3xl border border-border bg-popover shadow-sm outline-none">
          {children}
        </Popover.Popup>
      </Popover.Positioner>
    </Popover.Portal>
  </Popover.Root>
);
