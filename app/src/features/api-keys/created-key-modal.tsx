import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { useCopy } from "@/hooks/use-copy";
import { useVerifyCredential } from "@/hooks/use-verify-credential";
import type { CreatedApiKey } from "@/types/bigrag";

export const CreatedKeyModal = ({
  createdKey,
  onClose,
}: {
  createdKey: CreatedApiKey | null;
  onClose: () => void;
}) => {
  const { copied, copy } = useCopy();
  const { verifying: testingKey, verify } = useVerifyCredential();

  const testNewKey = () => {
    if (!createdKey) return;
    void verify(createdKey.key, {
      successMessage: "Key connected",
      errorMessage: "Key test failed",
    });
  };

  return (
    <Modal onClose={onClose} open={!!createdKey} title="Save this key">
      {createdKey && (
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground">
            This is the only time you'll see the full key. Copy it now.
          </p>
          <div className="break-all rounded-md border border-border bg-muted p-3 font-mono text-xs">
            {createdKey.key}
          </div>
          <div className="flex justify-end gap-2">
            <Button onClick={testNewKey} size="lg" variant="secondary" disabled={testingKey}>
              {testingKey ? "Testing…" : "Test connection"}
            </Button>
            <Button onClick={() => copy(createdKey.key)} size="lg">
              {copied ? (
                <>
                  <Check className="size-4" /> Copied
                </>
              ) : (
                <>
                  <Copy className="size-4" /> Copy key
                </>
              )}
            </Button>
          </div>
        </div>
      )}
    </Modal>
  );
};
