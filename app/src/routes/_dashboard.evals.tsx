import { createFileRoute } from "@tanstack/react-router";
import { PageHeader } from "@/components/ui/page-header";
import { EvalRunner } from "@/features/evals/eval-runner";

export const Route = createFileRoute("/_dashboard/evals")({
  component: () => <EvalsPage />,
});

const EvalsPage = () => (
  <div className="flex flex-col gap-6">
    <PageHeader
      title="Retrieval evaluation"
      description="Measure recall@k, MRR, and nDCG before changing chunking or embeddings."
    />
    <EvalRunner />
  </div>
);
