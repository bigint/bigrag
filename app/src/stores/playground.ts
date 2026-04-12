import { create } from "zustand";
import { persist } from "zustand/middleware";

export type PlaygroundSettings = {
  openaiKey: string;
  model: string;
  topK: number;
  systemPrompt: string;
  temperature: number;
};

type State = PlaygroundSettings & {
  update: <K extends keyof PlaygroundSettings>(k: K, v: PlaygroundSettings[K]) => void;
  reset: () => void;
};

const DEFAULT_SYSTEM =
  "You are a helpful assistant. Answer the user's question using ONLY the context below. " +
  "If the answer isn't in the context, say you don't know — don't make things up. " +
  "Cite chunk numbers like [1], [2] when you use them.";

const DEFAULTS: PlaygroundSettings = {
  openaiKey: "",
  model: "gpt-4o-mini",
  topK: 5,
  systemPrompt: DEFAULT_SYSTEM,
  temperature: 0.2,
};

export const usePlaygroundStore = create<State>()(
  persist(
    (set) => ({
      ...DEFAULTS,
      update: (k, v) => set((s) => ({ ...s, [k]: v })),
      reset: () => set(DEFAULTS),
    }),
    { name: "bigrag-playground" },
  ),
);

export const OPENAI_MODELS = [
  { value: "gpt-4o-mini", label: "GPT-4o mini" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4.1-mini", label: "GPT-4.1 mini" },
  { value: "gpt-4.1", label: "GPT-4.1" },
  { value: "gpt-3.5-turbo", label: "GPT-3.5 turbo" },
];
