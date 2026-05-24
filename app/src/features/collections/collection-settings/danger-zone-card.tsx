import { Trash2, TriangleAlert } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";

export const DangerZoneCard = ({
  collectionName,
  truncatePending,
  onTruncate,
  deletePending,
  onDelete,
}: {
  collectionName: string;
  truncatePending: boolean;
  onTruncate: () => Promise<void>;
  deletePending: boolean;
  onDelete: () => Promise<void>;
}) => {
  const [confirmDeleteOpen, setConfirmDeleteOpen] = useState(false);
  const [confirmTruncateOpen, setConfirmTruncateOpen] = useState(false);

  return (
    <>
      <Card className="border-destructive/40">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-destructive">
            <TriangleAlert className="size-4" />
            Danger zone
          </CardTitle>
          <CardDescription>Destructive actions cannot be undone.</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => setConfirmTruncateOpen(true)}>
            <Trash2 className="size-4" />
            Remove all documents
          </Button>
          <Button variant="destructive" onClick={() => setConfirmDeleteOpen(true)}>
            <Trash2 className="size-4" />
            Delete collection
          </Button>
        </CardContent>
      </Card>

      <ConfirmDialog
        open={confirmTruncateOpen}
        onClose={() => setConfirmTruncateOpen(false)}
        title="Remove all documents?"
        description="The collection stays, but all documents and vectors are removed."
        confirmLabel="Remove documents"
        confirmationLabel={`Type ${collectionName} to remove all documents`}
        confirmationText={collectionName}
        loading={truncatePending}
        onConfirm={async () => {
          await onTruncate();
          setConfirmTruncateOpen(false);
        }}
      />

      <ConfirmDialog
        open={confirmDeleteOpen}
        onClose={() => setConfirmDeleteOpen(false)}
        title={`Delete ${collectionName}?`}
        description="This permanently removes the collection, documents, and vectors."
        confirmLabel="Delete collection"
        confirmationLabel={`Type ${collectionName} to delete the collection`}
        confirmationText={collectionName}
        variant="destructive"
        loading={deletePending}
        onConfirm={onDelete}
      />
    </>
  );
};
