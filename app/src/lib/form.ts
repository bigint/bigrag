import type { FormEvent } from "react";

export const firstString = (values: readonly unknown[]) =>
  values.find((value): value is string => typeof value === "string") ?? null;

export const errorText = (values: readonly unknown[]) => {
  const message = values.filter((value): value is string => typeof value === "string").join(", ");
  return message || null;
};

export const submitWith =
  (handleSubmit: () => Promise<void> | void, beforeSubmit?: () => void) =>
  (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    beforeSubmit?.();
    void handleSubmit();
  };
