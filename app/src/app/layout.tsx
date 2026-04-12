import type { Metadata, Viewport } from "next";
import { Outfit } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";

const outfit = Outfit({ subsets: ["latin"] });

export const metadata: Metadata = {
  title: "bigRAG Studio",
  description: "Admin console for bigRAG — collections, documents, queries, API keys.",
  icons: { icon: "/favicon.ico" },
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: "#ffffff",
};

const RootLayout = ({ children }: { children: React.ReactNode }) => (
  <html lang="en">
    <body className={`${outfit.className} min-h-screen bg-background text-foreground antialiased`}>
      <a
        href="#main"
        className="sr-only focus:not-sr-only focus:absolute focus:top-2 focus:left-2 rounded-md bg-primary px-3 py-1.5 text-xs text-primary-foreground"
      >
        Skip to content
      </a>
      <Providers>{children}</Providers>
    </body>
  </html>
);

export default RootLayout;
