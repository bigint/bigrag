"use client";

import { Field } from "@base-ui/react/field";
import type { Ref, TextareaHTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface TextareaProps extends TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: string;
  error?: string | null;
  description?: string;
}

export const Textarea = ({
  className,
  label,
  error,
  description,
  id,
  ref,
  ...props
}: TextareaProps & { ref?: Ref<HTMLTextAreaElement> }) => (
  <Field.Root invalid={!!error} className="w-full">
    {label && (
      <Field.Label className="mb-1.5 block text-sm font-semibold" htmlFor={id}>
        {label}
      </Field.Label>
    )}
    <textarea
      id={id}
      ref={ref}
      className={cn(
        "min-h-24 w-full resize-y rounded-2xl border border-input bg-background px-4 py-3 text-sm transition-all",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
        error && "border-destructive focus-visible:ring-destructive",
        className,
      )}
      {...props}
    />
    {description && !error && (
      <Field.Description className="mt-1.5 text-xs text-muted-foreground">
        {description}
      </Field.Description>
    )}
    {error && <Field.Error className="mt-1.5 text-xs text-destructive">{error}</Field.Error>}
  </Field.Root>
);
