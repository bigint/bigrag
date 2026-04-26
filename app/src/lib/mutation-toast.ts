import { toast } from "sonner";

export const errorToast = (fallback: string) => (err: unknown) =>
  toast.error(err instanceof Error ? err.message : fallback);
