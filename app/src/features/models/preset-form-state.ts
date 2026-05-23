import type { EmbeddingPresetBody } from "@/hooks/use-embedding-presets";
import type { EmbeddingPreset } from "@/types/bigrag";

export type Provider = "openai" | "openai_compatible" | "cohere" | "voyage";

type EmbeddingModelCatalogItem = {
  description?: string;
  dimension: number;
  model: string;
  provider: string;
};

export type PresetFormValues = {
  apiKey: string;
  baseUrl: string;
  model: string;
  name: string;
  provider: Provider;
};

export const DEFAULT_MODELS: Record<Provider, { dimension: number; model: string }> = {
  openai: { model: "text-embedding-3-small", dimension: 1536 },
  openai_compatible: { model: "text-embedding-3-small", dimension: 1536 },
  cohere: { model: "embed-english-v3.0", dimension: 1024 },
  voyage: { model: "voyage-3.5", dimension: 1024 },
};

export const PROVIDER_OPTIONS = [
  { value: "openai", label: "OpenAI" },
  { value: "openai_compatible", label: "OpenAI-compatible" },
  { value: "cohere", label: "Cohere" },
  { value: "voyage", label: "Voyage AI" },
];

export const defaultPresetFormValues = (editing: EmbeddingPreset | null): PresetFormValues => {
  if (editing) {
    return {
      apiKey: "",
      baseUrl: editing.base_url ?? "",
      model: editing.model,
      name: editing.name,
      provider: editing.provider,
    };
  }
  return {
    apiKey: "",
    baseUrl: "",
    model: DEFAULT_MODELS.openai.model,
    name: "",
    provider: "openai",
  };
};

export const embeddingModelOptions = (
  models: readonly EmbeddingModelCatalogItem[] | undefined,
  provider: Provider,
) =>
  models
    ?.filter((model) => model.provider === provider)
    .map((model) => ({
      value: model.model,
      label: `${model.model} · ${model.dimension}d`,
    })) ?? [];

export const selectedEmbeddingDimension = ({
  editing,
  model,
  models,
  provider,
}: {
  editing: EmbeddingPreset | null;
  model: string;
  models: readonly EmbeddingModelCatalogItem[] | undefined;
  provider: Provider;
}) => {
  const match = models?.find((item) => item.provider === provider && item.model === model);
  if (match) return match.dimension;
  if (editing && editing.provider === provider && editing.model === model) return editing.dimension;
  return DEFAULT_MODELS[provider].dimension;
};

export const validatePresetFormValues = (
  values: PresetFormValues,
  editing: EmbeddingPreset | null,
): string | undefined => {
  if (!values.name.trim()) return "Name is required";
  if (!values.model.trim()) return "Model is required";
  if (!editing && !values.apiKey.trim()) return "API key is required";
  if (values.provider === "openai_compatible" && !values.baseUrl.trim()) {
    return "Base URL is required for OpenAI-compatible presets";
  }
  return undefined;
};

export const presetBodyFromValues = (
  values: PresetFormValues,
  dimension: number,
): Partial<EmbeddingPresetBody> => {
  const body: Partial<EmbeddingPresetBody> = {
    name: values.name.trim(),
    provider: values.provider,
    model: values.model.trim(),
    base_url: values.baseUrl.trim() || null,
    dimension,
  };
  if (values.apiKey.trim()) body.api_key = values.apiKey.trim();
  return body;
};
