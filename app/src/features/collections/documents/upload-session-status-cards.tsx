import { CircleAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Spinner } from "@/components/ui/spinner";

interface UploadSessionErrorCardProps {
  readonly message: string;
  readonly onDismiss: () => void;
  readonly onRetry: () => void;
}

export const UploadSessionErrorCard = ({
  message,
  onDismiss,
  onRetry,
}: UploadSessionErrorCardProps) => (
  <Card className="overflow-hidden rounded-xl border-destructive/25">
    <CardContent className="flex flex-wrap items-center justify-between gap-3 p-4">
      <div className="flex min-w-0 items-center gap-3">
        <CircleAlert className="size-4 text-destructive" />
        <span className="text-sm text-muted-foreground">{message}</span>
      </div>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="secondary" onClick={onRetry}>
          Retry
        </Button>
        <Button size="sm" variant="ghost" onClick={onDismiss}>
          Dismiss
        </Button>
      </div>
    </CardContent>
  </Card>
);

export const UploadSessionLoadingCard = () => (
  <Card className="overflow-hidden rounded-xl">
    <CardContent className="flex items-center gap-3 p-4">
      <Spinner size="sm" />
      <span className="text-sm text-muted-foreground">Loading upload session…</span>
    </CardContent>
  </Card>
);
