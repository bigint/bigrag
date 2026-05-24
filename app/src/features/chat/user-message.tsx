import { FilePenLine } from "lucide-react";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";
import { Textarea } from "@/components/ui/textarea";

export const UserMessage = ({
  content,
  id,
  onEdit,
}: {
  content: string;
  id: string;
  onEdit?: (messageId: string, content: string) => void;
}) => {
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);

  const openEdit = () => {
    setDraft(content);
    setEditing(true);
  };

  const submitEdit = () => {
    const trimmed = draft.trim();
    if (!trimmed || !onEdit) {
      setEditing(false);
      return;
    }
    onEdit(id, trimmed);
    setEditing(false);
  };

  return (
    <article className="group ml-auto max-w-[min(42rem,88%)] rounded-xl bg-muted px-4 py-3 text-sm font-semibold leading-6 text-foreground">
      <div className="flex items-start gap-3">
        <span className="whitespace-pre-wrap">{content}</span>
        {onEdit && (
          <button
            type="button"
            className="mt-0.5 inline-flex size-7 shrink-0 items-center justify-center rounded-md text-muted-foreground opacity-0 hover:bg-background hover:text-foreground group-hover:opacity-100"
            onClick={openEdit}
            aria-label="Edit message"
          >
            <FilePenLine className="size-3.5" />
          </button>
        )}
      </div>
      <Modal
        open={editing}
        onClose={() => setEditing(false)}
        title="Edit message"
        footer={
          <>
            <Button variant="secondary" onClick={() => setEditing(false)}>
              Cancel
            </Button>
            <Button onClick={submitEdit} disabled={!draft.trim()}>
              Save & resend
            </Button>
          </>
        }
      >
        <Textarea autoFocus onChange={(e) => setDraft(e.target.value)} rows={5} value={draft} />
      </Modal>
    </article>
  );
};
