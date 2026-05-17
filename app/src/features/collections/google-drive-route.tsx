import { getRouteApi } from "@tanstack/react-router";
import { GoogleDrivePanel } from "@/features/collections/google-drive-panel";

const routeApi = getRouteApi("/_dashboard/collections/$name/connectors/google-drive");

export const GoogleDriveConnector = () => {
  const { name: rawName } = routeApi.useParams();
  const name = decodeURIComponent(rawName);

  return <GoogleDrivePanel collection={name} />;
};
