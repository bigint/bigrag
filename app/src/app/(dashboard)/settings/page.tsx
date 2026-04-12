"use client";

import { useRouter, useSearchParams } from "next/navigation";
import { PageHeader } from "@/components/ui/page-header";
import { Tabs } from "@/components/ui/tabs";
import { AccountTab } from "./tabs/account-tab";
import { AuditTab } from "./tabs/audit-tab";
import { EvalTab } from "./tabs/eval-tab";
import { GdprTab } from "./tabs/gdpr-tab";
import { ServerTab } from "./tabs/server-tab";
import { UsageTab } from "./tabs/usage-tab";

const TABS = [
  { label: "Account", value: "account" },
  { label: "Server", value: "server" },
  { label: "Usage & cost", value: "usage" },
  { label: "Audit log", value: "audit" },
  { label: "Evaluation", value: "eval" },
  { label: "GDPR", value: "gdpr" },
];

const COMPONENTS: Record<string, React.FC> = {
  account: AccountTab,
  server: ServerTab,
  usage: UsageTab,
  audit: AuditTab,
  eval: EvalTab,
  gdpr: GdprTab,
};

const SettingsPage = () => {
  const router = useRouter();
  const params = useSearchParams();
  const tab = params.get("tab") ?? "account";

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
        description="Manage your account, inspect infrastructure health, review audit trails, measure retrieval quality, and run GDPR-style erasures."
      />
      <Tabs tabs={TABS} value={tab} onChange={setTab} />
      <div>
        <Active />
      </div>
    </div>
  );
};

export default SettingsPage;
