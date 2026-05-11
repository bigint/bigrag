import { RootProvider } from "fumadocs-ui/provider/next";
import { GeistMono } from "geist/font/mono";
import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import type { ReactNode } from "react";
import "./global.css";

export const metadata: Metadata = {
  description:
    "The open-source RAG platform you can self-host. Document ingestion, vector search, and retrieval-augmented generation on your own infrastructure.",
  title: {
    default: "bigRAG Docs",
    template: "%s — bigRAG",
  },
};

const outfit = Outfit({
  display: "swap",
  subsets: ["latin"],
  variable: "--font-outfit",
});

const Layout = ({ children }: { children: ReactNode }) => (
  <html className={`${outfit.variable} ${GeistMono.variable}`} lang="en">
    <body className="flex min-h-screen flex-col font-sans">
      <RootProvider theme={{ enabled: false }}>{children}</RootProvider>
    </body>
  </html>
);

export default Layout;
