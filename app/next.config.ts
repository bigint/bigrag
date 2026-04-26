import type { NextConfig } from "next";

// CSP that lets Next.js' inline hydration scripts run while clamping where
// the page is allowed to send data. The key constraint is `connect-src`:
// without an explicit allowlist, an XSS / hostile browser extension could
// exfiltrate the user's stored OpenAI key (and TanStack Query cache) to an
// attacker domain. Inline scripts stay allowed because Next.js' streaming
// RSC injects them; an XSS payload can still execute, but it cannot phone
// home to anywhere outside `self` and the OpenAI API.
const CSP = [
  "default-src 'self'",
  "script-src 'self' 'unsafe-inline' 'unsafe-eval'",
  "style-src 'self' 'unsafe-inline'",
  "img-src 'self' data: blob:",
  "font-src 'self' data:",
  "connect-src 'self' https://api.openai.com",
  "frame-ancestors 'none'",
  "form-action 'self'",
  "base-uri 'self'",
].join("; ");

const config: NextConfig = {
  reactStrictMode: true,
  output: "standalone",
  experimental: {
    optimizePackageImports: ["lucide-react", "motion", "@base-ui/react"],
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
          { key: "Content-Security-Policy", value: CSP },
        ],
      },
    ];
  },
};

export default config;
