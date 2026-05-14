"use client";

import { HomeAction, RetryAction, StatusPage, SupportAction } from "@/components/status-page";
import "./global.css";

type GlobalErrorPageProps = {
  readonly error: Error & { digest?: string };
  readonly reset: () => void;
};

const GlobalErrorPage = ({ error, reset }: GlobalErrorPageProps) => (
  <html lang="en">
    <body>
      <StatusPage
        actions={
          <>
            <RetryAction reset={reset} />
            <HomeAction />
            <SupportAction />
          </>
        }
        code="500"
        description="The docs shell could not recover this request. Retry once, then use the support link with the digest if it keeps failing."
        note={error.digest ? `Digest: ${error.digest}` : undefined}
        title="Application error"
      />
    </body>
  </html>
);

export default GlobalErrorPage;
