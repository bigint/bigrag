import { createFileRoute } from "@tanstack/react-router";
import { getModelsFocusGroup, getModelsTab } from "@/features/models/model-tabs";
import { ModelsPage } from "@/features/models/models-page";

type ModelsSearch = {
  group?: string;
  tab?: string;
};

export const Route = createFileRoute("/_dashboard/models")({
  validateSearch: (search: Record<string, unknown>): ModelsSearch => ({
    group: typeof search.group === "string" ? search.group : undefined,
    tab: typeof search.tab === "string" ? search.tab : undefined,
  }),
  component: () => {
    const search = Route.useSearch();
    return (
      <ModelsPage
        activeTab={getModelsTab(search.tab)}
        focusGroup={getModelsFocusGroup(search.group)}
      />
    );
  },
});
