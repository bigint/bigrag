import { Page } from "@/components/ui/page";
import { EvalRunner } from "@/features/evals/eval-runner";

export const EvalsPage = () => (
  <Page.Shell>
    <Page.Header
      className="mb-0"
      title="Retrieval evaluation"
      description="Measure recall@k, MRR, and nDCG before changing chunking or embeddings."
    />
    <EvalRunner />
  </Page.Shell>
);
