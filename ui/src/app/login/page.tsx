"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Logo } from "@/components/logo";
import { getClient } from "@/lib/client";
import { setSessionToken, setUser } from "@/lib/auth-store";

const LoginPage = () => {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      const res = await getClient().login({ email, password });
      setSessionToken(res.token);
      setUser(res.user as Parameters<typeof setUser>[0]);
      router.replace("/");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-bg">
      <div className="w-full max-w-sm px-4">
        <div className="mb-8 flex flex-col items-center gap-3">
          <Logo size={40} />
          <h1 className="text-2xl font-semibold tracking-tight text-text">
            bigRAG
          </h1>
          <p className="text-sm text-text-muted">Sign in to your account</p>
        </div>

        <div className="rounded-lg border border-border bg-bg-card p-6">
          {error && (
            <div className="mb-4 rounded-md border border-danger/20 bg-danger/10 px-3 py-2.5 text-sm text-danger">
              {error}
            </div>
          )}

          <form className="space-y-4" onSubmit={handleSubmit}>
            <div>
              <label
                className="mb-1.5 block text-sm text-text-muted"
                htmlFor="email"
              >
                Email
              </label>
              <input
                autoComplete="email"
                className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none placeholder:text-text-dim focus:border-text-muted"
                id="email"
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                required
                type="email"
                value={email}
              />
            </div>

            <div>
              <label
                className="mb-1.5 block text-sm text-text-muted"
                htmlFor="password"
              >
                Password
              </label>
              <input
                autoComplete="current-password"
                className="w-full rounded-md border border-border bg-bg px-3 py-2 text-sm text-text outline-none placeholder:text-text-dim focus:border-text-muted"
                id="password"
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••"
                required
                type="password"
                value={password}
              />
            </div>

            <button
              className="w-full rounded-md bg-text px-4 py-2 text-sm font-medium text-bg transition-opacity hover:opacity-90 disabled:opacity-50"
              disabled={loading}
              type="submit"
            >
              {loading ? "Signing in…" : "Sign in"}
            </button>
          </form>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
