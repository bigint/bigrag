import type { Metadata } from "next";
import { DocsAction, HomeAction, StatusPage } from "@/components/status-page";

export const metadata: Metadata = {
  title: "Page not found",
};

const NotFound = () => (
  <StatusPage
    actions={
      <>
        <HomeAction />
        <DocsAction />
      </>
    }
    code="404"
    description="The page you opened is not part of the current bigRAG docs. Start from the docs index, or return home."
    title="Page not found"
  />
);

export default NotFound;
