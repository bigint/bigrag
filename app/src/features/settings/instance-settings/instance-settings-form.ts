import { useForm } from "@tanstack/react-form";
import type { InstanceSettingsFormValues } from "@/features/settings/instance-settings-form-state";

export const useInstanceSettingsForm = () =>
  useForm({
    defaultValues: {} as InstanceSettingsFormValues,
  });

export type InstanceSettingsForm = ReturnType<typeof useInstanceSettingsForm>;
