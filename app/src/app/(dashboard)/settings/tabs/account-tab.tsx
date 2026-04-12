"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { useChangePassword, useLogout, useLogoutAll, useSession } from "@/hooks/use-auth";
import { formatRelative } from "@/lib/format";

export const AccountTab = () => {
  const router = useRouter();
  const { data: session } = useSession();
  const changePassword = useChangePassword();
  const logout = useLogout();
  const logoutAll = useLogoutAll();

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
          <CardDescription>
            You'll be signed out of all sessions after changing it.
          </CardDescription>
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
          <CardTitle>Active sessions</CardTitle>
          <CardDescription>
            Sign out of every browser or device where your account is logged in.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex justify-start">
          <Button
            variant="outline"
            disabled={logoutAll.isPending}
            onClick={async () => {
              if (
                !window.confirm(
                  "Sign out of every device? You'll need to log in again everywhere.",
                )
              ) {
                return;
              }
              try {
                await logoutAll.mutateAsync();
                router.replace("/login");
              } catch (err) {
                toast.error(err instanceof Error ? err.message : "Failed");
              }
            }}
          >
            {logoutAll.isPending ? "Signing out…" : "Sign out of all devices"}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
};
