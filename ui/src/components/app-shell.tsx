"use client";

import { AuthGuard } from "./auth-guard";
import { Sidebar } from "./sidebar";

export const AppShell = ({
  children
}: {
  readonly children: React.ReactNode;
}) => (
  <AuthGuard>
    <Sidebar />
    <main className="ml-56 min-h-screen">
      <div className="px-8 py-6">{children}</div>
    </main>
  </AuthGuard>
);
