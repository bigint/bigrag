import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import type { SearchMode } from "@/features/collections/collection-settings/use-collection-settings-draft";

export const RetrievalDefaultsCard = ({
  description,
  onDescriptionChange,
  topK,
  onTopKChange,
  searchMode,
  onSearchModeChange,
  rerankingEnabled,
  onRerankingChange,
  dirty,
  saving,
  onSave,
}: {
  description: string;
  onDescriptionChange: (value: string) => void;
  topK: number;
  onTopKChange: (value: number) => void;
  searchMode: SearchMode;
  onSearchModeChange: (value: SearchMode) => void;
  rerankingEnabled: boolean;
  onRerankingChange: (value: boolean) => void;
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
}) => (
  <Card>
    <CardHeader>
      <CardTitle>Retrieval defaults</CardTitle>
      <CardDescription>Update query defaults and reranking for this collection.</CardDescription>
    </CardHeader>
    <CardContent className="flex flex-col gap-4">
      <Textarea
        label="Description"
        description={dirty ? "Unsaved changes" : undefined}
        value={description}
        onChange={(e) => onDescriptionChange(e.target.value)}
      />
      <div className="grid gap-4 sm:grid-cols-3">
        <Input
          label="Default top K"
          type="number"
          min={1}
          max={200}
          value={topK}
          onChange={(e) => onTopKChange(Number(e.target.value))}
        />
        <Select
          label="Search mode"
          value={searchMode}
          onChange={(v) => onSearchModeChange(v as SearchMode)}
          options={[
            { value: "semantic", label: "Semantic" },
            { value: "keyword", label: "Keyword" },
            { value: "hybrid", label: "Hybrid" },
          ]}
        />
        <Switch
          className="sm:pt-6"
          label="Reranking enabled"
          checked={rerankingEnabled}
          onCheckedChange={onRerankingChange}
        />
      </div>
      <div>
        <Button onClick={onSave} disabled={saving || !dirty}>
          Save defaults
        </Button>
      </div>
    </CardContent>
  </Card>
);
