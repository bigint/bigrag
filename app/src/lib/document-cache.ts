import type { Document } from "@/types/bigrag";
import type { Paginated } from "@/types/pagination";

export type DocListResponse = Paginated<"documents", Document>;

export type DocumentPageParam = {
  cursor: string | null;
  offset: number;
  mode: "cursor" | "offset";
};

export type DocumentStatusUpdate = Pick<
  Document,
  "chunk_count" | "error_message" | "id" | "multimodal_element_count" | "progress" | "status"
>;

export type BatchStatusResponse = {
  documents: DocumentStatusUpdate[];
  total: number;
};
