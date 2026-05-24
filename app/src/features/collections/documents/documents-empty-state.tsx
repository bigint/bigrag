import { FileText } from "lucide-react";
import { Empty } from "@/components/ui/empty";

export const DocumentsEmptyState = ({ filtered }: { filtered: boolean }) => (
  <Empty
    icon={<FileText className="size-6" />}
    title={filtered ? "No matching documents" : "No documents yet"}
    description={
      filtered
        ? "Adjust filters to see more documents."
        : "Upload files above and they will appear here as they ingest."
    }
  />
);
