import { toast } from "sonner";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import type { Document } from "@/types/bigrag";

interface DeleteDocumentDialogsProps {
  readonly deleteDoc: { id: string; filename: string } | null;
  readonly onCloseDelete: () => void;
  readonly onConfirmDelete: (id: string) => Promise<void>;
  readonly deletePending: boolean;
  readonly bulkOpen: boolean;
  readonly onCloseBulk: () => void;
  readonly onConfirmBulk: (ids: string[]) => Promise<void>;
  readonly bulkPending: boolean;
  readonly selectedDocuments: Document[];
}

export const DeleteDocumentDialogs = ({
  deleteDoc,
  onCloseDelete,
  onConfirmDelete,
  deletePending,
  bulkOpen,
  onCloseBulk,
  onConfirmBulk,
  bulkPending,
  selectedDocuments,
}: DeleteDocumentDialogsProps) => {
  const bulkConfirmationText = `DELETE ${selectedDocuments.length}`;
  return (
    <>
      <ConfirmDialog
        confirmLabel="Delete"
        description={
          deleteDoc
            ? `Delete "${deleteDoc.filename}"? This removes the document and its vectors.`
            : ""
        }
        loading={deletePending}
        onClose={onCloseDelete}
        onConfirm={async () => {
          if (!deleteDoc) return;
          try {
            await onConfirmDelete(deleteDoc.id);
          } catch (err) {
            toast.error(err instanceof Error ? err.message : "Delete failed");
          }
        }}
        open={!!deleteDoc}
        title="Delete document"
      />
      <ConfirmDialog
        confirmLabel="Delete selected"
        confirmationLabel={`Type ${bulkConfirmationText} to confirm`}
        confirmationText={bulkConfirmationText}
        description={`This permanently removes ${selectedDocuments.length} document${selectedDocuments.length === 1 ? "" : "s"} and their vectors.`}
        loading={bulkPending}
        onClose={onCloseBulk}
        onConfirm={async () => {
          const ids = selectedDocuments.map((doc) => doc.id);
          if (!ids.length) return;
          await onConfirmBulk(ids);
        }}
        open={bulkOpen}
        title="Delete selected documents"
      />
    </>
  );
};
