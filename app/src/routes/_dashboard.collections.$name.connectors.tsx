import { createFileRoute, Outlet, useRouterState } from "@tanstack/react-router";
import { Cloud } from "lucide-react";
import { LinkTabs } from "@/components/ui/tabs";

export const Route = createFileRoute("/_dashboard/collections/$name/connectors")({
  component: () => <ConnectorsLayout />,
});

const ConnectorsLayout = () => {
  const { name: rawName } = Route.useParams();
  const name = decodeURIComponent(rawName);
  const pathname = useRouterState({ select: (state) => state.location.pathname });
  const base = `/collections/${encodeURIComponent(name)}/connectors`;
  const tabs = [
    {
      href: `${base}/google-drive`,
      label: "Google Drive",
      icon: Cloud,
    },
  ].map((tab) => ({
    ...tab,
    active: pathname === tab.href || pathname.startsWith(`${tab.href}/`),
  }));

  return (
    <div className="flex flex-col gap-5">
      <LinkTabs className="mb-0" tabs={tabs} />
      <Outlet />
    </div>
  );
};
