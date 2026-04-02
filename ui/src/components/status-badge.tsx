import { match, P } from "ts-pattern";

export const StatusBadge = ({ status }: { status: string }) => {
  const { color, dot } = match(status)
    .with(P.union("ready", "indexed"), () => ({
      color: "bg-bg-hover text-text",
      dot: "bg-text"
    }))
    .with(P.union("building", "indexing"), () => ({
      color: "bg-bg-hover text-text-muted",
      dot: "bg-text-muted animate-pulse"
    }))
    .otherwise(() => ({
      color: "bg-bg-hover text-text-muted",
      dot: "bg-text-dim"
    }));

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium shrink-0 ${color}`}
    >
      <span className={`size-1.5 rounded-full ${dot}`} />
      {status}
    </span>
  );
};
