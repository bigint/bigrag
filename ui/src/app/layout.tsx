import { GeistMono } from "geist/font/mono";
import type { Metadata } from "next";
import { Outfit } from "next/font/google";
import { Providers } from "@/lib/query-client";
import "./globals.css";

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit"
});

export const metadata: Metadata = {
  description: "Admin dashboard for bigRAG vector database",
  icons: {
    icon: "/logo.svg"
  },
  title: "bigRAG Admin"
};

const RootLayout = ({ children }: { readonly children: React.ReactNode }) => {
  return (
    <html className={`${outfit.variable} ${GeistMono.variable}`} lang="en">
      <body className="antialiased">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
};

export default RootLayout;
