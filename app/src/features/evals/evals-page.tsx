import { PageHeader } from "@/components/ui/page-header";
import { PageShell } from "@/components/ui/page-shell";
import { EvalRunner } from "@/features/evals/eval-runner";

export const EvalsPage = () => (
  <PageShell>
    <PageHeader
      className="mb-0"
      title="Retrieval evaluation"
      description="Measure recall@k, MRR, and nDCG before changing chunking or embeddings."
    />
    <EvalRunner />
  </PageShell>
);
