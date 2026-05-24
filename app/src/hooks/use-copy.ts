import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

const RESET_MS = 1800;

export const useCopy = () => {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | null>(null);

  useEffect(
    () => () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    },
    [],
  );

  const copy = async (text: string, successMessage = "Copied") => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      toast.success(successMessage);
      if (timer.current !== null) window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), RESET_MS);
    } catch {
      toast.error("Couldn't copy — select and copy manually");
    }
  };

  return { copied, copy };
};
