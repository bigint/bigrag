import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";

export const DocumentElementsCard = ({
  multimodalEnabled,
  multimodalEnrichmentEnabled,
  onToggleMultimodal,
  onToggleEnrichment,
  dirty,
  saving,
  onSave,
}: {
  multimodalEnabled: boolean;
  multimodalEnrichmentEnabled: boolean;
  onToggleMultimodal: (enabled: boolean) => void;
  onToggleEnrichment: (enabled: boolean) => void;
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
}) => (
  <Card>
    <CardHeader>
      <CardTitle>Document elements</CardTitle>
      <CardDescription>
        Preserve structure and optional LLM summaries for multimodal retrieval.
      </CardDescription>
    </CardHeader>
    <CardContent className="flex flex-col gap-4">
      <Switch
        label="Store document elements"
        checked={multimodalEnabled}
        onCheckedChange={onToggleMultimodal}
      />
      <Switch
        label="LLM enrichment"
        checked={multimodalEnrichmentEnabled}
        onCheckedChange={onToggleEnrichment}
      />
      <div>
        <Button onClick={onSave} disabled={saving || !dirty}>
          Save document elements
        </Button>
      </div>
    </CardContent>
  </Card>
);
