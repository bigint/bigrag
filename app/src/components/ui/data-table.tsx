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
      <div className="rounded-3xl border border-border bg-card p-12 text-center">
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
    <div className="overflow-x-auto rounded-3xl border border-border bg-surface p-1.5">
      <table className="w-full min-w-2xl border-separate border-spacing-y-1 text-sm">
        <thead>
          <tr>
            {columns.map((col) => (
              <th
                key={col.key}
                className={cn(
                  "px-3 py-2.5 text-left text-xs font-semibold text-muted-foreground sm:px-5",
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
            <tr key={keyExtractor(item)} className="group">
              {columns.map((col) => (
                <td
                  key={col.key}
                  className={cn(
                    "bg-background px-3 py-3 tabular-nums first:rounded-l-2xl last:rounded-r-2xl group-hover:bg-muted sm:px-5 sm:py-3.5",
                    col.className,
                  )}
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
