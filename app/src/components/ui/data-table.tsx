"use client";

import type { ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Empty } from "./empty";
import { Spinner } from "./spinner";

export interface Column<T> {
  readonly key: string;
  readonly header: string;
  readonly className?: string;
  readonly headerClassName?: string;
  readonly render: (item: T, index: number) => ReactNode;
}

interface DataTableProps<T> {
  readonly columns: Column<T>[];
  readonly data: T[];
  readonly keyExtractor: (item: T) => string;
  readonly loading?: boolean;
  readonly loadingMessage?: string;
  readonly emptyIcon?: ReactNode;
  readonly emptyTitle?: string;
  readonly emptyDescription?: string;
  readonly emptyAction?: ReactNode;
}

export const DataTable = <T,>({
  columns,
  data,
  keyExtractor,
  loading = false,
  loadingMessage = "Loading…",
  emptyIcon,
  emptyTitle = "No data",
  emptyDescription,
  emptyAction,
}: DataTableProps<T>) => {
  if (loading) {
    return (
      <div className="rounded-xl border border-border p-12 text-center">
        <Spinner className="mx-auto" />
        <p className="mt-3 text-sm text-muted-foreground">{loadingMessage}</p>
      </div>
    );
  }
  if (data.length === 0) {
    return (
      <Empty
        action={emptyAction}
        description={emptyDescription}
        icon={emptyIcon}
        title={emptyTitle}
      />
    );
  }
  return (
    <div className="overflow-hidden overflow-x-auto rounded-xl border border-border">
      <table className="w-full min-w-[600px] border-collapse text-sm">
        <thead>
          <tr className="border-b border-border">
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-3 py-2.5 text-left text-xs font-medium uppercase tracking-wide text-muted-foreground sm:px-5 sm:py-3",
                  col.headerClassName,
                )}
              >
                {col.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((item, idx) => (
            <tr
              key={keyExtractor(item)}
              className={cn(
                "transition-colors hover:bg-muted/30",
                idx !== data.length - 1 && "border-b border-border",
              )}
            >
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn("px-3 py-3 tabular-nums sm:px-5 sm:py-4", col.className)}
                >
                  {col.render(item, idx)}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
