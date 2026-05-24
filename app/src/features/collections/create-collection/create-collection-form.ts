import { useForm } from "@tanstack/react-form";
import {
  type CreateCollectionFormValues,
  defaultCreateCollectionFormValues,
  validateCreateCollectionFormValues,
} from "@/features/collections/collection-form-state";

export const DEFAULT_METADATA_SCHEMA = '{\n  "type": "object"\n}';

export const useCreateCollectionForm = (
  onValidSubmit: (value: CreateCollectionFormValues) => Promise<void>,
) =>
  useForm({
    defaultValues: defaultCreateCollectionFormValues(),
    validators: {
      onSubmit: ({ value }) => validateCreateCollectionFormValues(value),
    },
    onSubmit: async ({ value }) => {
      await onValidSubmit(value);
    },
  });

export type CreateCollectionForm = ReturnType<typeof useCreateCollectionForm>;
