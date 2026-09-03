import type { Document } from "@/types/bigrag";
import type { Paginated } from "@/types/pagination";

export type DocListResponse = Paginated<"documents", Document>;

export type DocumentPageParam = {
  cursor: string | null;
  offset: number;
  mode: "cursor" | "offset";
};
