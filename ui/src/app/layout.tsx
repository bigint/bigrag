import type { Metadata } from "next";
import { GeistSans } from "geist/font/sans";
import { GeistMono } from "geist/font/mono";
import { Sidebar } from "@/components/sidebar";
import "./globals.css";

export const metadata: Metadata = {
  title: "bigRAG Admin",
  description: "Admin dashboard for bigRAG vector database",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${GeistSans.variable} ${GeistMono.variable} dark`}>
      <body className="antialiased">
        <Sidebar />
        <main className="ml-56 min-h-screen">
          <div className="px-8 py-6">{children}</div>
        </main>
      </body>
    </html>
  );
}
