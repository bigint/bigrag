import type { DocumentListOrder, DocumentListSort } from "@/hooks/use-documents";
import type { UploadSession } from "@/types/bigrag";

export const documentsPageSize = 25;

export type DocumentsTabFilters = {
  order: DocumentListOrder;
  q: string;
  sort: DocumentListSort;
  status: string;
};

export const defaultDocumentsTabFilters: DocumentsTabFilters = {
  order: "desc",
  q: "",
  sort: "created_at",
  status: "",
};

export const shouldDismissUploadSession = (session: UploadSession) =>
  (session.status === "complete" || session.status === "failed" || session.status === "canceled") &&
  session.active_files === 0 &&
  session.failed_files === 0;

export const getErrorStatus = (error: unknown) => {
  if (!error || typeof error !== "object") return undefined;
  const { response, status } = error as { response?: unknown; status?: unknown };
  if (typeof status === "number") return status;
  if (!response || typeof response !== "object") return undefined;
  const { status: responseStatus } = response as { status?: unknown };
  return typeof responseStatus === "number" ? responseStatus : undefined;
};

export const acceptedDescription = (allowed: string[]) =>
  allowed.length
    ? `Only ${allowed.map((type) => `.${type}`).join(", ")} allowed in this collection.`
    : "PDF, DOCX, PPTX, MD, HTML, TXT, images — ingested automatically.";
