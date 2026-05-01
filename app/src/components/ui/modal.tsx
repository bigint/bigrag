"use client";

import { Dialog } from "@base-ui/react/dialog";
import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { backdropMotion, popupMotion } from "@/lib/dialog-motion";

interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
  size?: "sm" | "md" | "lg" | "xl";
}

const sizeMap = {
  sm: "max-w-sm",
  md: "max-w-md",
  lg: "max-w-lg",
  xl: "max-w-6xl",
};

export const Modal = ({ open, onClose, title, children, footer, size = "md" }: ModalProps) => {
  const isReduced = useReducedMotion();
  return (
    <Dialog.Root
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      open={open}
    >
      <AnimatePresence>
        {open && (
          <Dialog.Portal>
            <Dialog.Backdrop
              render={
                <motion.div
                  className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm"
                  {...backdropMotion(isReduced)}
                />
              }
            />
            <Dialog.Popup
              render={
                <motion.div
                  className={cn(
                    "fixed inset-x-4 top-1/2 z-50 max-h-dvh -translate-y-1/2 overflow-y-auto rounded-3xl border border-border bg-background sm:left-1/2 sm:right-auto sm:w-full sm:-translate-x-1/2",
                    sizeMap[size],
                  )}
                  {...popupMotion(isReduced)}
                />
              }
            >
              <div className="flex items-center justify-between px-6 pt-5 pb-3">
                <Dialog.Title className="text-base font-semibold">{title}</Dialog.Title>
                <Dialog.Close
                  aria-label="Close"
                  className="rounded-full p-1.5 text-muted-foreground transition-colors hover:bg-accent hover:text-accent-foreground"
                >
                  <svg
                    aria-hidden="true"
                    className="size-4"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth={2}
                    viewBox="0 0 24 24"
                  >
                    <title>Close</title>
                    <path d="M6 18L18 6M6 6l12 12" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </Dialog.Close>
              </div>
              <div className="px-6 pb-5">{children}</div>
              {footer && (
                <div className="flex justify-end gap-2 border-t border-border bg-muted/45 px-6 py-4">
                  {footer}
                </div>
              )}
            </Dialog.Popup>
          </Dialog.Portal>
        )}
      </AnimatePresence>
    </Dialog.Root>
  );
};
