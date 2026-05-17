import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import {
  collectionConnectorProviders,
  connectorCollectionHref,
} from "@/features/connectors/connector-catalog";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors/")({
  component: () => <ConnectorsIndex />,
});

const ConnectorsIndex = () => {
  const { name } = Route.useParams();
  const navigate = useNavigate();

  useRedirectToDefaultConnector(name, navigate);

  return (
    <div className="flex justify-center py-12">
      <Spinner />
    </div>
  );
};

const useRedirectToDefaultConnector = (name: string, navigate: ReturnType<typeof useNavigate>) => {
  useEffect(() => {
    const provider = collectionConnectorProviders[0];
    if (!provider) return;
    navigate({
      to: connectorCollectionHref(decodeCollectionName(name), provider),
      replace: true,
    });
  }, [name, navigate]);
};
