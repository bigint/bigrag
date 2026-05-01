import { PageHeader } from "@/components/ui/page-header";
import { EvalRunner } from "./components/eval-runner";

const EvalsPage = () => (
  <div className="flex flex-col gap-6">
    <PageHeader
      title="Retrieval evaluation"
      description="Measure recall@k, MRR, and nDCG before changing chunking or embeddings."
    />
    <EvalRunner />
  </div>
);

export default EvalsPage;
