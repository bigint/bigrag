import { getRouteApi } from "@tanstack/react-router";
import { GoogleDrivePanel } from "@/features/collections/google-drive-panel";
import { decodeCollectionName } from "@/features/collections/use-collection-name";

const routeApi = getRouteApi("/_dashboard/collections/$name/connectors/google-drive");

export const GoogleDriveConnector = () => {
  const { name: rawName } = routeApi.useParams();
  const name = decodeCollectionName(rawName);

  return <GoogleDrivePanel collection={name} />;
};
