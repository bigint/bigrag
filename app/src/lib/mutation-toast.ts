import { APIError } from "@bigrag/client/browser";
import { toast } from "sonner";

export const errorToast =
  (fallback: string, byStatus?: Record<number, string>) => (err: unknown) => {
    if (byStatus && err instanceof APIError) {
      const override = byStatus[err.status];
      if (override) {
        toast.error(override);
        return;
      }
    }
    toast.error(err instanceof Error ? err.message : fallback);
  };
