"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { useEffect } from "react";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { AccountTab } from "./tabs/account-tab";
import { AuditTab } from "./tabs/audit-tab";
import { ServerTab } from "./tabs/server-tab";
import { UsageTab } from "./tabs/usage-tab";

const TABS = [
  { label: "Account", value: "account" },
  { label: "Server", value: "server" },
  { label: "Usage & cost", value: "usage" },
  { label: "Audit log", value: "audit" },
];

const COMPONENTS: Record<string, React.FC> = {
  account: AccountTab,
  server: ServerTab,
  usage: UsageTab,
  audit: AuditTab,
};

const SettingsPage = () => {
  const router = useRouter();
  const params = useSearchParams();
  const tab = params.get("tab") ?? "account";

  useEffect(() => {
    if (tab === "eval") {
      router.replace("/evals");
    }
  }, [router, tab]);

  const setTab = (value: string) => {
    const next = new URLSearchParams(params.toString());
    next.set("tab", value);
    router.replace(`?${next.toString()}`);
  };

  const Active = COMPONENTS[tab] ?? AccountTab;

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Instance settings"
        description="Manage your account, inspect infrastructure health, and review audit trails."
      />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <div>
        <Active />
      </div>
    </div>
  );
};

export default SettingsPage;
