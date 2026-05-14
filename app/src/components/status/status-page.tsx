import { Link } from "@tanstack/react-router";
import { ArrowLeft, Home, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "@/components/brand/logo";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

const actionClassName =
  "inline-flex h-9 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

type StatusPageProps = {
  readonly code: string;
  readonly title: string;
  readonly description: string;
  readonly children?: ReactNode;
};

export const StatusPage = ({ children, code, description, title }: StatusPageProps) => (
  <main
    id="main"
    className="flex min-h-dvh items-center justify-center bg-background px-4 py-10 text-foreground"
  >
    <Card className="w-full max-w-xl p-6 sm:p-8">
      <div className="flex items-center justify-between gap-4">
        <Logo />
        <span className="rounded-md border border-border bg-muted px-2.5 py-1 font-mono text-muted-foreground text-xs">
          {code}
        </span>
      </div>
      <div className="mt-12">
        <p className="font-mono text-muted-foreground text-xs uppercase tracking-[0.2em]">
          bigRAG admin
        </p>
        <h1 className="mt-3 text-3xl font-semibold tracking-normal sm:text-4xl">{title}</h1>
        <p className="mt-3 max-w-md text-muted-foreground text-sm leading-6">{description}</p>
      </div>
      {children && <div className="mt-6 flex flex-col gap-3 sm:flex-row">{children}</div>}
    </Card>
  </main>
);

export const AppNotFoundPage = () => (
  <StatusPage
    code="404"
    description="This admin route does not exist. Check the URL, or return to a known workspace page."
    title="Page not found"
  >
    <Link className={cn(actionClassName, "bg-primary text-primary-foreground")} to="/overview">
      <Home className="size-4" />
      Overview
    </Link>
    <Link className={cn(actionClassName, "border border-border bg-background")} to="/collections">
      <ArrowLeft className="size-4" />
      Collections
    </Link>
  </StatusPage>
);

type AppErrorPageProps = {
  readonly reset: () => void;
};

export const AppErrorPage = ({ reset }: AppErrorPageProps) => (
  <StatusPage
    code="500"
    description="The admin UI hit an unexpected error while rendering this page. Retry the route, or return to overview."
    title="Something went wrong"
  >
    <button
      className={cn(actionClassName, "bg-primary text-primary-foreground")}
      onClick={reset}
      type="button"
    >
      <RefreshCcw className="size-4" />
      Try again
    </button>
    <Link className={cn(actionClassName, "border border-border bg-background")} to="/overview">
      <Home className="size-4" />
      Overview
    </Link>
  </StatusPage>
);
