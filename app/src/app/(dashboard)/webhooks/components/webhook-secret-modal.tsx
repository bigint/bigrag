"use client";

import { Check, Copy } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

interface Props {
  secret: string | null;
  onClose: () => void;
}

export const WebhookSecretModal = ({ secret, onClose }: Props) => {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    if (!secret) return;
    await navigator.clipboard.writeText(secret);
    setCopied(true);
    toast.success("Secret copied");
    setTimeout(() => setCopied(false), 1800);
  };

  return (
    <Modal onClose={onClose} open={!!secret} title="Signing secret">
      {secret && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            Save this now — we won't show it again. Use it to verify HMAC signatures on incoming
            payloads.
          </p>
          <div className="break-all rounded-md border border-border bg-muted p-3 font-mono text-xs">
            {secret}
          </div>
          <div className="flex justify-end">
            <Button onClick={copy}>
              {copied ? (
                <>
                  <Check className="size-4" /> Copied
                </>
              ) : (
                <>
                  <Copy className="size-4" /> Copy secret
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
