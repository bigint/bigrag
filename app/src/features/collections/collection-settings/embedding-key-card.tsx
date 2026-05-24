import { KeyRound } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

export const EmbeddingKeyCard = ({
  status,
  value,
  onChange,
  saving,
  onSave,
}: {
  status: string;
  value: string;
  onChange: (value: string) => void;
  saving: boolean;
  onSave: () => void;
}) => (
  <Card>
    <CardHeader>
      <CardTitle className="flex items-center gap-2">
        <KeyRound className="size-4" />
        Embedding key
      </CardTitle>
      <CardDescription>
        {status}. Saving a new key stores it on this collection without changing the model.
      </CardDescription>
    </CardHeader>
    <CardContent className="flex flex-col gap-3">
      <Input
        label="New API key"
        type="password"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="sk-..."
      />
      <div>
        <Button onClick={onSave} disabled={saving || !value.trim()}>
          Update embedding key
        </Button>
      </div>
    </CardContent>
  </Card>
);
