import type { Metadata, Viewport } from "next";
import "./globals.css";
import { ThemeInit } from "@/components/theme-init";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "bigRAG Studio",
  description: "Admin console for bigRAG — collections, documents, queries, API keys.",
  icons: { icon: "/favicon.ico" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#fafaf9" },
    { media: "(prefers-color-scheme: dark)", color: "#0c0a09" },
  ],
};

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="en" suppressHydrationWarning>
    <body>
      <ThemeInit />
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 rounded-md bg-[var(--color-primary)] px-3 py-1.5 text-xs text-[var(--color-primary-foreground)]"
      >
        Skip to content
      </a>
      <Providers>{children}</Providers>
    </body>
  </html>
);

export default RootLayout;
