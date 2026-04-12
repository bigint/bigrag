"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHeader } from "@/components/ui/page-header";
import { useChangePassword, useLogout, useSession } from "@/hooks/use-auth";
import { useReadiness } from "@/hooks/use-platform";
import { formatRelative } from "@/lib/format";

const SettingsPage = () => {
  const router = useRouter();
  const { data: session } = useSession();
  const changePassword = useChangePassword();
  const logout = useLogout();
  const { data: readiness } = useReadiness();

  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [confirm, setConfirm] = useState("");

  const save = async (e: React.FormEvent) => {
    e.preventDefault();
    if (next !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      await changePassword.mutateAsync({ current_password: current, new_password: next });
      toast.success("Password updated");
      await logout.mutateAsync();
      router.replace("/login");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed");
    }
  };

  return (
    <div className="flex flex-col gap-6">
      <PageHeader title="Settings" description="Manage your account and inspect server health." />

      <Card>
        <CardHeader>
          <CardTitle>Your account</CardTitle>
          <CardDescription>Signed in as {session?.user.email}</CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <Input label="Display name" defaultValue={session?.user.display_name} disabled />
          <Input
            label="Last sign-in"
            value={session?.user.last_login_at ? formatRelative(session.user.last_login_at) : "—"}
            disabled
          />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change password</CardTitle>
          <CardDescription>You'll be signed out of all sessions after changing it.</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={save} className="flex flex-col gap-3">
            <Input
              label="Current password"
              type="password"
              value={current}
              onChange={(e) => setCurrent(e.target.value)}
              required
            />
            <Input
              label="New password"
              type="password"
              minLength={8}
              value={next}
              onChange={(e) => setNext(e.target.value)}
              required
            />
            <Input
              label="Confirm new password"
              type="password"
              minLength={8}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
            <div className="flex justify-end">
              <Button type="submit" disabled={changePassword.isPending}>
                {changePassword.isPending ? "Updating…" : "Change password"}
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Server</CardTitle>
          <CardDescription>
            {readiness
              ? `Running bigRAG v${readiness.version} — ${readiness.status}`
              : "Checking readiness…"}
          </CardDescription>
        </CardHeader>
        <CardContent className="grid gap-3 sm:grid-cols-2">
          <Row label="Postgres" ok={readiness?.postgres} />
          <Row label="Milvus" ok={readiness?.milvus} />
          <Row label="Redis" ok={readiness?.redis} />
          <Row label="Embeddings" ok={readiness?.embedding} />
        </CardContent>
      </Card>
    </div>
  );
};

const Row = ({ label, ok }: { label: string; ok: boolean | undefined }) => (
  <div className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
    <span>{label}</span>
    <span
      className={
        ok === undefined
          ? "text-muted-foreground"
          : ok
            ? "font-medium text-success"
            : "font-medium text-destructive"
      }
    >
      {ok === undefined ? "—" : ok ? "operational" : "down"}
    </span>
  </div>
);

export default SettingsPage;
