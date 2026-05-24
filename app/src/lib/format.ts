import { formatDistanceToNowStrict } from "date-fns";

export const formatBytes = (bytes: number): string => {
  if (!bytes) return "0 B";
  const units = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(1024));
  return `${(bytes / 1024 ** i).toFixed(i === 0 ? 0 : 1)} ${units[i]}`;
};

export const formatNumber = (n: number): string =>
  new Intl.NumberFormat("en", { notation: n >= 10_000 ? "compact" : "standard" }).format(n);

export const formatRelative = (iso: string | Date | null | undefined): string => {
  if (!iso) return "—";
  const d = iso instanceof Date ? iso : new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return `${formatDistanceToNowStrict(d)} ago`;
};

export const formatRelativeOrNever = (iso: string | Date | null | undefined): string =>
  iso ? formatRelative(iso) : "never";
