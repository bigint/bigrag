"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useSetup, useSetupStatus } from "@/hooks/use-auth";

const useRedirectIfSetupComplete = () => {
  const router = useRouter();
  const { data: status, isPending } = useSetupStatus();
  useEffect(() => {
    if (!isPending && status && !status.needs_setup) router.replace("/login");
  }, [isPending, status, router]);
};

const SetupPage = () => {
  const router = useRouter();
  const setup = useSetup();
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");

  useRedirectIfSetupComplete();

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (password !== confirm) {
      toast.error("Passwords do not match");
      return;
    }
    try {
      await setup.mutateAsync({ email, password, display_name: displayName });
      toast.success("Admin account created");
      router.replace("/overview");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Setup failed");
    }
  };

  return (
    <div className="w-full max-w-md rounded-xl border border-border bg-card p-6">
      <div className="mb-5 flex flex-col gap-1">
        <div className="inline-flex items-center gap-2 self-start rounded-full bg-accent px-2 py-0.5 text-xs font-medium text-accent-foreground">
          First-time setup
        </div>
        <h1 className="font-semibold text-lg tracking-tight">Create the first admin</h1>
        <p className="text-sm text-muted-foreground">
          This account owns the Studio. You can invite more admins after signing in.
        </p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4">
        <Input
          label="Display name"
          autoComplete="name"
          value={displayName}
          onChange={(e) => setDisplayName(e.target.value)}
          placeholder="Ada Lovelace"
        />
        <Input
          label="Email"
          type="email"
          autoComplete="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Input
          label="Password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          description="At least 8 characters."
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Input
          label="Confirm password"
          type="password"
          autoComplete="new-password"
          required
          minLength={8}
          value={confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button type="submit" size="lg" disabled={setup.isPending}>
          {setup.isPending ? "Creating account…" : "Create admin & sign in"}
        </Button>
      </form>
    </div>
  );
};

export default SetupPage;
