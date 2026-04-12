"use client";

import { Dialog as BaseDialog } from "@base-ui/react/dialog";
import { X } from "lucide-react";
import { cn } from "@/lib/cn";

type RootProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  children: React.ReactNode;
};

export const Dialog = ({ open, onOpenChange, children }: RootProps) => (
  <BaseDialog.Root open={open} onOpenChange={onOpenChange}>
    {children}
  </BaseDialog.Root>
);

export const DialogTrigger = BaseDialog.Trigger;

export const DialogContent = ({
  title,
  description,
  children,
  className,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
  className?: string;
}) => (
  <BaseDialog.Portal>
    <BaseDialog.Backdrop className="fixed inset-0 z-40 bg-black/40 backdrop-blur-[2px] data-[open]:animate-in data-[open]:fade-in data-[closed]:animate-out data-[closed]:fade-out" />
    <BaseDialog.Popup
      className={cn(
        "fixed left-1/2 top-1/2 z-50 w-full max-w-lg -translate-x-1/2 -translate-y-1/2",
        "rounded-xl border border-[var(--color-border)] bg-[var(--color-card)] shadow-[var(--shadow-lg)]",
        "focus:outline-none",
        "data-[open]:animate-in data-[open]:fade-in data-[open]:zoom-in-95",
        "data-[closed]:animate-out data-[closed]:fade-out data-[closed]:zoom-out-95",
        className,
      )}
    >
      <div className="flex items-start justify-between gap-4 px-6 pt-5 pb-3">
        <div className="flex flex-col gap-1">
          <BaseDialog.Title className="font-semibold text-base tracking-tight">
            {title}
          </BaseDialog.Title>
          {description && (
            <BaseDialog.Description className="text-sm text-[var(--color-muted-foreground)]">
              {description}
            </BaseDialog.Description>
          )}
        </div>
        <BaseDialog.Close
          className="rounded-md p-1 text-[var(--color-muted-foreground)] hover:bg-[var(--color-accent)] hover:text-[var(--color-accent-foreground)]"
          aria-label="Close"
        >
          <X className="h-4 w-4" />
        </BaseDialog.Close>
      </div>
      <div className="px-6 pb-6">{children}</div>
    </BaseDialog.Popup>
  </BaseDialog.Portal>
);

export const DialogClose = BaseDialog.Close;
