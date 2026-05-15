import { TriangleAlert } from "lucide-react";
import { cn } from "@/lib/cn";
import type { WorkerAvailability } from "./worker-status";

export const WorkerOfflineBanner = ({
  availability,
  className,
  compact = false,
  message,
}: {
  availability: WorkerAvailability;
  className?: string;
  compact?: boolean;
  message?: string;
}) => {
  if (!availability.offline) return null;
  return (
    <div
      className={cn(
        "rounded-md border border-warning/30 bg-warning/10 text-warning",
        compact ? "px-3 py-2 text-xs" : "px-4 py-3 text-sm",
        className,
      )}
      role="alert"
    >
      <div className="flex items-start gap-2">
        <TriangleAlert className={cn("mt-0.5 shrink-0", compact ? "size-3.5" : "size-4")} />
        <div className="min-w-0">
          <div className="font-semibold">{availability.title}</div>
          <div className={cn(!compact && "mt-0.5")}>{message ?? availability.message}</div>
          <div className="mt-1 text-warning/80">
            {availability.heartbeatAgeLabel
              ? `Last heartbeat ${availability.heartbeatAgeLabel}.`
              : "No worker heartbeat has been recorded."}
          </div>
        </div>
      </div>
    </div>
  );
};
