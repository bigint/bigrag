"use client";

import { AlertDialog } from "@base-ui/react/alert-dialog";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { backdropMotion, popupMotion } from "@/lib/dialog-motion";
import { Button } from "./button";

interface ConfirmDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onConfirm: () => void;
  readonly title: string;
  readonly description: string;
  readonly confirmLabel?: string;
  readonly loading?: boolean;
  readonly variant?: "destructive" | "primary";
}

export const ConfirmDialog = ({
  open,
  onClose,
  onConfirm,
  title,
  description,
  confirmLabel = "Confirm",
  loading = false,
  variant = "destructive",
}: ConfirmDialogProps) => {
  const isReduced = useReducedMotion();
  return (
    <AlertDialog.Root
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      open={open}
    >
      <AnimatePresence>
        {open && (
          <AlertDialog.Portal>
            <AlertDialog.Backdrop
              render={
                <motion.div
                  className="fixed inset-0 z-50 bg-black/50"
                  {...backdropMotion(isReduced)}
                />
              }
            />
            <AlertDialog.Popup
              render={
                <motion.div
                  className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-background shadow-xl"
                  {...popupMotion(isReduced)}
                />
              }
            >
              <div className="px-6 py-5">
                <AlertDialog.Title className="text-base font-semibold">{title}</AlertDialog.Title>
                <AlertDialog.Description className="mt-2 text-sm text-muted-foreground">
                  {description}
                </AlertDialog.Description>
              </div>
              <div className="flex justify-end gap-2 border-t border-border px-6 py-4">
                <AlertDialog.Close
                  disabled={loading}
                  render={<Button variant="secondary">Cancel</Button>}
                />
                <Button disabled={loading} onClick={onConfirm} variant={variant}>
                  {loading ? "Processing…" : confirmLabel}
                </Button>
              </div>
            </AlertDialog.Popup>
          </AlertDialog.Portal>
        )}
      </AnimatePresence>
    </AlertDialog.Root>
  );
};
