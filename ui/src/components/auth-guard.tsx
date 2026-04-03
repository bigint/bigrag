"use client";

import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { APIError } from "@bigrag/client";
import { getClient } from "@/lib/client";
import { clearAuth, isAuthenticated, setUser } from "@/lib/auth-store";

const PUBLIC_PATHS = ["/login", "/setup"];

export const AuthGuard = ({
  children
}: {
  readonly children: React.ReactNode;
}) => {
  const router = useRouter();
  const pathname = usePathname();
  const [checked, setChecked] = useState(false);
  const [authorized, setAuthorized] = useState(false);

  const check = useCallback(async () => {
    const isPublic = PUBLIC_PATHS.some((p) => pathname.startsWith(p));

    try {
      const status = await getClient().getSetupStatus();
      if (status.auth_required === false) {
        if (isPublic) {
          router.replace("/");
          setChecked(true);
          return;
        }
        setAuthorized(true);
        setChecked(true);
        return;
      }
      if (status.needs_setup) {
        if (pathname !== "/setup") {
          router.replace("/setup");
        }
        setChecked(true);
        return;
      }
    } catch (err) {
      if (err instanceof APIError && err.status >= 500) {
        // Server error — don't silently grant access, let the user see the problem
        setChecked(true);
        return;
      }
      // Network error or 404 (no setup endpoint) — legacy mode, allow through
      setAuthorized(true);
      setChecked(true);
      return;
    }

    if (isPublic) {
      if (isAuthenticated() && pathname === "/login") {
        router.replace("/");
      }
      setAuthorized(true);
      setChecked(true);
      return;
    }

    if (!isAuthenticated()) {
      router.replace("/login");
      setChecked(true);
      return;
    }

    try {
      const { user } = await getClient().getMe();
      setUser(user as Parameters<typeof setUser>[0]);
      setAuthorized(true);
    } catch {
      clearAuth();
      router.replace("/login");
    } finally {
      setChecked(true);
    }
  }, [pathname, router]);

  useEffect(() => {
    check();
  }, [check]);

  if (!checked) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="size-5 animate-spin rounded-full border-2 border-border border-t-text" />
      </div>
    );
  }

  if (!authorized) return null;

  return <>{children}</>;
};
