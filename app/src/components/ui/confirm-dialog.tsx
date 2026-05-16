import { AlertDialog } from "@base-ui/react/alert-dialog";
import { useEffect, useState } from "react";
import { Button } from "./button";
import { Input } from "./input";

interface ConfirmDialogProps {
  readonly open: boolean;
  readonly onClose: () => void;
  readonly onConfirm: () => void | Promise<void>;
  readonly title: string;
  readonly description: string;
  readonly confirmLabel?: string;
  readonly confirmationLabel?: string;
  readonly confirmationText?: string;
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
  confirmationLabel,
  confirmationText,
  loading = false,
  variant = "destructive",
}: ConfirmDialogProps) => {
  const [typed, setTyped] = useState("");
  const needsConfirmation = Boolean(confirmationText);
  const canConfirm = !confirmationText || typed === confirmationText;

  useEffect(() => {
    if (!open) setTyped("");
  }, [open]);

  return (
    <AlertDialog.Root
      onOpenChange={(o) => {
        if (!o) onClose();
      }}
      open={open}
    >
      <AlertDialog.Portal>
        <AlertDialog.Backdrop
          render={<div className="fixed inset-0 z-50 bg-black/30 backdrop-blur-sm" />}
        />
        <AlertDialog.Popup
          render={
            <div className="fixed inset-x-4 top-1/2 z-50 max-w-sm -translate-y-1/2 rounded-xl border border-border bg-background sm:left-1/2 sm:right-auto sm:w-full sm:-translate-x-1/2" />
          }
        >
          <div className="px-6 py-5">
            <AlertDialog.Title className="text-base font-semibold">{title}</AlertDialog.Title>
            <AlertDialog.Description className="mt-2 text-sm text-muted-foreground">
              {description}
            </AlertDialog.Description>
            {confirmationText && (
              <div className="mt-4">
                <Input
                  autoComplete="off"
                  label={confirmationLabel ?? `Type ${confirmationText} to confirm`}
                  onChange={(event) => setTyped(event.target.value)}
                  value={typed}
                />
              </div>
            )}
          </div>
          <div className="flex justify-end gap-2 border-t border-border bg-muted/45 px-6 py-4">
            <AlertDialog.Close
              disabled={loading}
              render={<Button variant="secondary">Cancel</Button>}
            />
            <Button
              disabled={loading || (needsConfirmation && !canConfirm)}
              onClick={onConfirm}
              variant={variant}
            >
              {loading ? "Processing…" : confirmLabel}
            </Button>
          </div>
        </AlertDialog.Popup>
      </AlertDialog.Portal>
    </AlertDialog.Root>
  );
};
