import { useEffect, useState } from "react";
import type { Document } from "@/types/bigrag";

export const useDocumentsTabState = (documents: Document[]) => {
  const [selected, setSelected] = useState<Set<string>>(() => new Set());

  const selectedDocuments = documents.filter((doc) => selected.has(doc.id));
  const selectedVisibleCount = selectedDocuments.length;
  const allVisibleSelected = documents.length > 0 && selectedVisibleCount === documents.length;

  useEffect(() => {
    setSelected((current) => {
      const visible = new Set(documents.map((doc) => doc.id));
      const next = new Set([...current].filter((id) => visible.has(id)));
      return next.size === current.size ? current : next;
    });
  }, [documents]);

  const toggleVisibleSelection = () => {
    setSelected((current) => {
      const next = new Set(current);
      if (allVisibleSelected) {
        for (const doc of documents) next.delete(doc.id);
      } else {
        for (const doc of documents) next.add(doc.id);
      }
      return next;
    });
  };

  const toggleDocumentSelection = (id: string) => {
    setSelected((current) => {
      const next = new Set(current);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const clearSelection = () => setSelected(new Set());

  return {
    selected,
    selectedDocuments,
    allVisibleSelected,
    toggleVisibleSelection,
    toggleDocumentSelection,
    clearSelection,
  };
};
