"use client";

import { Field } from "@base-ui/react/field";
import type { InputHTMLAttributes, Ref } from "react";
import { cn } from "@/lib/cn";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  label?: string;
  error?: string | null;
  description?: string;
  trailing?: React.ReactNode;
}

export const Input = ({
  className,
  label,
  error,
  description,
  trailing,
  ref,
  ...props
}: InputProps & { ref?: Ref<HTMLInputElement> }) => (
  <Field.Root invalid={!!error} className="w-full">
    {label && <Field.Label className="mb-1.5 block text-sm font-semibold">{label}</Field.Label>}
    <div className="relative">
      <Field.Control
        className={cn(
          "h-10 w-full rounded-full border border-input bg-background px-4 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "data-[invalid]:border-destructive data-[invalid]:focus-visible:ring-destructive",
          trailing && "pr-12",
          className,
        )}
        ref={ref}
        render={<input />}
        {...props}
      />
      {trailing && (
        <div className="absolute inset-y-0 right-4 flex items-center text-muted-foreground">
          {trailing}
        </div>
      )}
    </div>
    {description && !error && (
      <Field.Description className="mt-1.5 text-xs text-muted-foreground">
        {description}
      </Field.Description>
    )}
    {error && <Field.Error className="mt-1.5 text-xs text-destructive">{error}</Field.Error>}
  </Field.Root>
);
