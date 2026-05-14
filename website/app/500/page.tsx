import type { Metadata } from "next";
import { DocsAction, HomeAction, StatusPage, SupportAction } from "@/components/status-page";

export const metadata: Metadata = {
  title: "Server error",
};

const ServerErrorPage = () => (
  <StatusPage
    actions={
      <>
        <HomeAction />
        <DocsAction />
        <SupportAction />
      </>
    }
    code="500"
    description="The docs app could not complete the request. If this keeps happening, share the route and deployment logs with the operator."
    title="Server error"
  />
);

export default ServerErrorPage;
