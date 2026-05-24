export const FileType = ({ type }: { type: string }) => (
  <div className="flex size-9 shrink-0 items-center justify-center rounded-md border border-border bg-muted text-[10px] font-semibold uppercase tracking-wide text-muted-foreground">
    {type.slice(0, 4) || "?"}
  </div>
);
