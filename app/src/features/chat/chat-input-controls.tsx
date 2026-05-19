import {
  Button,
  Checkbox,
  cn,
  Input,
  Popover,
  SegmentedControl,
  Slider,
  Textarea,
} from "@atelier/ui";
import { Check, Sparkles } from "lucide-react";
import type { ReactElement, ReactNode } from "react";
import type { Collection } from "@/types/bigrag";

export const OPENAI_MODELS = [
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

export type ChatPatch = Partial<ChatState> & { openaiKey?: string };
export const KeyMenu = ({
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
    <Input
      aria-label="OpenAI API key"
      autoComplete="off"
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

export const ModelMenu = ({
  onChange,
  value,
}: {
  onChange: (v: string) => void;
  value: string;
}) => (
  <div className="w-[min(18rem,calc(100vw-2rem))] p-1.5">
    {OPENAI_MODELS.map((model) => (
      <Button
        key={model.value}
        onClick={() => onChange(model.value)}
        variant="ghost"
        className={cn(
          "h-10 w-full justify-start rounded-md px-3 text-left text-sm font-normal",
          model.value === value && "bg-accent font-semibold text-foreground",
        )}
      >
        <Sparkles className="size-4 shrink-0 text-warning" />
        <span className="flex-1 truncate">{model.label}</span>
        {model.value === value && <Check className="size-4" />}
      </Button>
    ))}
  </div>
);

export const CollectionMenu = ({
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
      <Button
        key={collection.id}
        onClick={() => onChange(collection.name)}
        variant="ghost"
        className={cn(
          "min-h-11 w-full justify-start rounded-md px-3 text-left text-sm font-normal",
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
      </Button>
    ))}
  </div>
);

export const SettingsMenu = ({
  onPatch,
  saving,
  state,
}: {
  onPatch: (patch: ChatPatch) => void;
  saving: boolean;
  state: ChatState;
}) => (
  <div className="w-[min(24rem,calc(100vw-2rem))] space-y-4 p-4">
    <Slider
      label="Temperature"
      max={1}
      min={0}
      step={0.1}
      value={state.temperature}
      valueLabel={state.temperature.toFixed(1)}
      onValueChange={(value) => onPatch({ temperature: value })}
    />
    <Slider
      label="Top K chunks"
      max={20}
      min={1}
      step={1}
      value={state.topK}
      valueLabel={String(state.topK)}
      onValueChange={(value) => onPatch({ topK: Math.round(value) })}
    />

    <div className="space-y-2">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        Search mode
      </span>
      <SegmentedControl
        aria-label="Search mode"
        className="grid-cols-3"
        onChange={(searchMode) => onPatch({ searchMode })}
        options={[
          { label: "Semantic", value: "semantic" },
          { label: "Keyword", value: "keyword" },
          { label: "Hybrid", value: "hybrid" },
        ]}
        value={state.searchMode}
      />
    </div>

    <div className="flex items-center justify-between gap-3 rounded-lg border border-border px-3 py-2.5">
      <span>
        <span className="block text-sm font-semibold">Rerank when configured</span>
        <span className="block text-xs text-muted-foreground">
          Uses the collection reranker if available.
        </span>
      </span>
      <Checkbox
        aria-label="Use reranker when configured"
        checked={state.rerank}
        onCheckedChange={(checked) => onPatch({ rerank: checked })}
      />
    </div>

    <div className="space-y-2">
      <span className="text-xs font-semibold uppercase tracking-[0.14em] text-muted-foreground">
        System prompt
      </span>
      <Textarea
        aria-label="System prompt"
        className="min-h-28 rounded-lg px-3 py-2 text-xs leading-5"
        onChange={(e) => onPatch({ systemPrompt: e.target.value })}
        value={state.systemPrompt}
      />
    </div>
    {saving && <div className="text-xs text-muted-foreground">Saving...</div>}
  </div>
);

export const ToolbarPopover = ({
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
  <Popover
    align={align}
    onOpenChange={onOpenChange}
    open={open}
    side="top"
    sideOffset={8}
    trigger={trigger}
  >
    {children}
  </Popover>
);
