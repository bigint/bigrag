import { getRouteApi } from "@tanstack/react-router";
import { S3ConnectorPanel } from "@/features/collections/s3-connector-panel";
import { decodeCollectionName } from "@/features/collections/use-collection-name";

const routeApi = getRouteApi("/_dashboard/collections/$name/connectors/s3");

export const S3Connector = () => {
  const { name: rawName } = routeApi.useParams();
  const name = decodeCollectionName(rawName);

  return <S3ConnectorPanel collection={name} />;
};
