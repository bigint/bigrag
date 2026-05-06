"use client";

import { Cloud } from "lucide-react";
import { usePathname } from "next/navigation";
import { use } from "react";
import { LinkTabs } from "@/components/ui/tabs";

const ConnectorsLayout = ({
  children,
  params,
}: {
  children: React.ReactNode;
  params: Promise<{ name: string }>;
}) => {
  const { name: rawName } = use(params);
  const name = decodeURIComponent(rawName);
  const pathname = usePathname();
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
      {children}
    </div>
  );
};

export default ConnectorsLayout;
