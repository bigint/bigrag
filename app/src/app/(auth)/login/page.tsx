"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { toast } from "sonner";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { useLogin, useSetupStatus } from "@/hooks/use-auth";

const useRedirectIfSetupNeeded = (needsSetup: boolean | undefined) => {
  const router = useRouter();
  useEffect(() => {
    if (needsSetup) router.replace("/setup");
  }, [needsSetup, router]);
};

const LoginPage = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const login = useLogin();
  const { data: setupStatus, isPending, isError, error } = useSetupStatus();

  useRedirectIfSetupNeeded(setupStatus?.needs_setup);

  if (isPending || setupStatus?.needs_setup) {
    return (
      <div className="flex min-h-[240px] w-full items-center justify-center">
        <Spinner size="lg" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="w-full max-w-sm rounded-xl border border-destructive/40 bg-card p-6 shadow-md">
        <h1 className="font-semibold text-base">Can't reach bigRAG</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          {error instanceof Error ? error.message : "Unknown error"}
        </p>
        <p className="mt-3 text-xs text-muted-foreground">
          Make sure the bigRAG server is running at{" "}
          <code className="rounded bg-muted px-1 py-0.5 font-mono">
            {process.env.NEXT_PUBLIC_BIGRAG_URL ?? "http://localhost:6100"}
          </code>
          .
        </p>
      </div>
    );
  }

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      await login.mutateAsync({ email, password });
      router.replace("/overview");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Login failed");
    }
  };

  return (
    <div className="w-full max-w-sm rounded-xl border border-border bg-card p-6 shadow-md">
      <div className="mb-5 flex flex-col gap-1">
        <h1 className="font-semibold text-lg tracking-tight">Sign in</h1>
        <p className="text-sm text-muted-foreground">
          Manage your collections, documents, and API keys.
        </p>
      </div>
      <form onSubmit={submit} className="flex flex-col gap-4">
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
          autoComplete="current-password"
          required
          minLength={8}
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" disabled={login.isPending} size="lg">
          {login.isPending ? "Signing in…" : "Sign in"}
        </Button>
      </form>
    </div>
  );
};

export default LoginPage;
