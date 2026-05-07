import { createFileRoute } from "@tanstack/react-router";
import { GoogleDrivePanel } from "@/features/collections/google-drive-panel";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors/google-drive")({
  component: () => <GoogleDriveConnector />,
});

const GoogleDriveConnector = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);

  return <GoogleDrivePanel collection={name} />;
};
