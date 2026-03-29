export function StatusBadge({ status }: { status: string }) {
  const isReady = status === "ready" || status === "indexed";
  const isBuilding = status === "building" || status === "indexing";

  let colorClasses: string;
  if (isReady) {
    colorClasses = "bg-success/10 text-success";
  } else if (isBuilding) {
    colorClasses = "bg-warning/10 text-warning";
  } else {
    colorClasses = "bg-bg-hover text-text-muted";
  }

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-[11px] font-medium shrink-0 ${colorClasses}`}
    >
      <span
        className={`size-1.5 rounded-full ${
          isReady
            ? "bg-success"
            : isBuilding
              ? "bg-warning animate-pulse"
              : "bg-text-dim"
        }`}
      />
      {status}
    </span>
  );
}
