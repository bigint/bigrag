import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { LinkTabs } from "@/components/ui/tabs";
import { decodeCollectionName } from "@/features/collections/use-collection-name";
import {
  collectionConnectorProviders,
  connectorCollectionHref,
} from "@/features/connectors/connector-catalog";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors")({
  component: () => <ConnectorsLayout />,
});

const ConnectorsLayout = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeCollectionName(rawName);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const tabs = collectionConnectorProviders.map((provider) => {
    const href = connectorCollectionHref(name, provider);
    return {
      active: pathname === href || pathname.startsWith(`${href}/`),
      href,
      icon: provider.icon,
      label: provider.label,
    };
  });

  return (
    <div className="flex flex-col gap-6">
      <LinkTabs className="mb-0" tabs={tabs} />
      <Outlet />
    </div>
  );
};
