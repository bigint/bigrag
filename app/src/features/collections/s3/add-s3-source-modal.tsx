import { Modal } from "@/components/ui/modal";
import { S3SourceForm } from "@/features/collections/s3/s3-source-form";
import type { defaultS3SourceFormValues } from "@/features/collections/s3-source-form-state";

export const AddS3SourceModal = ({
  isPending,
  onClose,
  onSubmit,
  open,
  workerOffline,
}: {
  isPending: boolean;
  onClose: () => void;
  onSubmit: (value: ReturnType<typeof defaultS3SourceFormValues>) => Promise<void>;
  open: boolean;
  workerOffline: boolean;
}) => (
  <Modal onClose={onClose} open={open} size="lg" title="Add source">
    <S3SourceForm
      isPending={isPending}
      onCancel={onClose}
      onSubmit={onSubmit}
      workerOffline={workerOffline}
    />
  </Modal>
);
