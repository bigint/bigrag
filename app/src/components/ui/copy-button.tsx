import { Check, Copy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tooltip } from "@/components/ui/tooltip";
import { useCopy } from "@/hooks/use-copy";

export const CopyButton = ({ code, label }: { code: string; label: string }) => {
  const { copied, copy } = useCopy();
  return (
    <Tooltip content={copied ? "Copied" : "Copy"}>
      <Button
        aria-label={`Copy ${label}`}
        className="h-7 w-7 p-0"
        onClick={() => copy(code)}
        size="sm"
        variant="secondary"
      >
        {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      </Button>
    </Tooltip>
  );
};
