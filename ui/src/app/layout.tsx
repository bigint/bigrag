import { GeistMono } from "geist/font/mono";
import { GeistSans } from "geist/font/sans";
import type { Metadata } from "next";
import { Sidebar } from "@/components/sidebar";
import { Providers } from "@/lib/query-client";
import "./globals.css";

export const metadata: Metadata = {
  description: "Admin dashboard for bigRAG vector database",
  title: "bigRAG Admin"
};

const RootLayout = ({ children }: { readonly children: React.ReactNode }) => {
  return (
    <html className={`${GeistSans.variable} ${GeistMono.variable}`} lang="en">
      <body className="antialiased">
        <Providers>
          <Sidebar />
          <main className="ml-56 min-h-screen">
            <div className="px-8 py-6">{children}</div>
          </main>
        </Providers>
      </body>
    </html>
  );
};

export default RootLayout;
