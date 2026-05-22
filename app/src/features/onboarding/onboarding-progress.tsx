import { CheckCircle2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";

export const ProgressPanel = ({
  embeddingComplete,
  onFinish,
  setupComplete,
  vectorStorageComplete,
}: {
  readonly embeddingComplete: boolean;
  readonly onFinish: () => void;
  readonly setupComplete: boolean;
  readonly vectorStorageComplete: boolean;
}) => (
  <aside className="rounded-md border border-border bg-card p-4 xl:sticky xl:top-6 xl:self-start">
    <div className="font-semibold text-sm">Setup progress</div>
    <div className="mt-4 flex flex-col gap-3">
      <ProgressRow complete={embeddingComplete} label="Embedding preset" required />
      <ProgressRow complete={vectorStorageComplete} label="Vector storage" required />
    </div>
    <Button className="mt-5 w-full" disabled={!setupComplete} onClick={onFinish}>
      <CheckCircle2 className="size-4" />
      Finish setup
    </Button>
  </aside>
);

const ProgressRow = ({
  complete,
  label,
  required = false,
}: {
  readonly complete: boolean;
  readonly label: string;
  readonly required?: boolean;
}) => (
  <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-muted/25 px-3 py-2">
    <span className="text-sm">{label}</span>
    <Badge variant={complete ? "success" : required ? "warning" : "neutral"}>
      {complete ? "done" : required ? "required" : "optional"}
    </Badge>
  </div>
);
