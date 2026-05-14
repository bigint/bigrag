"use client";

import { DocsAction, RetryAction, StatusPage } from "@/components/status-page";

type ErrorPageProps = {
  readonly error: Error & { digest?: string };
  readonly reset: () => void;
};

const ErrorPage = ({ error, reset }: ErrorPageProps) => (
  <StatusPage
    actions={
      <>
        <RetryAction reset={reset} />
        <DocsAction />
      </>
    }
    code="500"
    description="The docs app hit an unexpected rendering error. Retry the request, or continue from the docs index."
    note={error.digest ? `Digest: ${error.digest}` : undefined}
    title="Something went wrong"
  />
);

export default ErrorPage;
