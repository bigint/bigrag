import { formatNumber } from "@/lib/format";

export const formatPercent = (value: number | undefined) =>
  `${Number.isFinite(value) ? (value ?? 0).toFixed(1) : "0.0"}%`;

export const formatMs = (value: number | undefined) => `${formatNumber(Math.round(value ?? 0))} ms`;

export const clampPercent = (value: number | undefined) => Math.max(0, Math.min(100, value ?? 0));

export const queueHealthVariant = (
  status: string | undefined,
): "error" | "neutral" | "success" | "warning" => {
  if (status === "ok") return "success";
  if (status === "down") return "error";
  if (status === "degraded") return "warning";
  return "neutral";
};
