import { createFileRoute } from "@tanstack/react-router";
import { CollectionSettings } from "@/features/collections/collection-settings/collection-settings";
import { decodeCollectionName } from "@/features/collections/use-collection-name";

const CollectionSettingsRoute = () => {
  const { name: rawName } = Route.useParams();
  return <CollectionSettings name={decodeCollectionName(rawName)} />;
};

export const Route = createFileRoute("/_dashboard/collections/$name/settings")({
  component: CollectionSettingsRoute,
});
