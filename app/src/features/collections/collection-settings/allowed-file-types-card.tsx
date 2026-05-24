import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Checkbox } from "@/components/ui/checkbox";
import { ALL_FILE_TYPES, FILE_TYPE_CATEGORIES } from "@/lib/file-types";

export const AllowedFileTypesCard = ({
  allowedTypes,
  onSelectAll,
  onClearAll,
  onToggleType,
  onToggleCategory,
  dirty,
  saving,
  onSave,
}: {
  allowedTypes: Set<string>;
  onSelectAll: () => void;
  onClearAll: () => void;
  onToggleType: (type: string) => void;
  onToggleCategory: (types: string[]) => void;
  dirty: boolean;
  saving: boolean;
  onSave: () => void;
}) => {
  const allSelected = allowedTypes.size === ALL_FILE_TYPES.length;
  const noneSelected = allowedTypes.size === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle>Allowed file types</CardTitle>
        <CardDescription>
          Restrict uploads by extension. Leave all selected to allow the default ingest set.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="flex flex-wrap gap-2">
          <Button variant="secondary" onClick={onSelectAll} disabled={allSelected}>
            Select all
          </Button>
          <Button variant="secondary" onClick={onClearAll} disabled={noneSelected}>
            Clear all
          </Button>
        </div>
        <div className="grid gap-4 md:grid-cols-3">
          {Object.entries(FILE_TYPE_CATEGORIES).map(([category, types]) => {
            const allInCategory = types.every((t) => allowedTypes.has(t));
            return (
              <div key={category} className="rounded-md border border-border p-3">
                <Checkbox
                  checked={allInCategory}
                  label={category}
                  onCheckedChange={() => onToggleCategory(types)}
                />
                <div className="mt-3 grid grid-cols-2 gap-2">
                  {types.map((t) => (
                    <Checkbox
                      key={t}
                      checked={allowedTypes.has(t)}
                      label={`.${t}`}
                      onCheckedChange={() => onToggleType(t)}
                    />
                  ))}
                </div>
              </div>
            );
          })}
        </div>
        <div>
          <Button onClick={onSave} disabled={saving || !dirty}>
            Save file types
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};
