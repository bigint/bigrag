import type { ErrorComponentProps } from "@tanstack/react-router";
import { Link } from "@tanstack/react-router";
import { ArrowLeft, Home, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";
import { Logo } from "@/components/brand/logo";
import { Card } from "@/components/ui/card";
import { cn } from "@/lib/cn";

const actionClassName =
  "inline-flex h-9 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background";

const isErrorRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null;

const getStringProperty = (value: unknown, key: string) =>
  isErrorRecord(value) && typeof value[key] === "string" ? value[key] : undefined;

const stringifyErrorValue = (value: unknown): string => {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean" || typeof value === "bigint") {
    return String(value);
  }
  if (value instanceof Error) return value.message || value.name;
  if (isErrorRecord(value)) {
    const message =
      getStringProperty(value, "message") ??
      getStringProperty(value, "detail") ??
      getStringProperty(value, "statusText");
    if (message) return message;
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  }
  return "No error message was provided.";
};

const getErrorCause = (error: unknown) =>
  error instanceof Error ? error.cause : isErrorRecord(error) ? error.cause : undefined;

const getErrorDetails = (error: unknown) => {
  const name = error instanceof Error ? error.name : getStringProperty(error, "name");
  const cause = getErrorCause(error);
  const digest = getStringProperty(error, "digest");
  const details = [
    {
      label: "Message",
      value: stringifyErrorValue(error),
    },
  ];

  if (name && name !== "Error") details.unshift({ label: "Type", value: name });
  if (cause) details.push({ label: "Cause", value: stringifyErrorValue(cause) });
  if (digest) details.push({ label: "Digest", value: digest });

  return details;
};

const reloadPage = () => window.location.reload();

type StatusPageDetail = {
  readonly label: string;
  readonly value: string;
};

type StatusPageProps = {
  readonly code: string;
  readonly title: string;
  readonly description: string;
  readonly details?: readonly StatusPageDetail[];
  readonly children?: ReactNode;
};

const StatusPage = ({ children, code, description, details, title }: StatusPageProps) => (
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
        {details && details.length > 0 && (
          <div
            className="mt-5 max-h-72 overflow-auto rounded-md border border-border bg-muted/40 p-4"
            role="alert"
          >
            <p className="font-mono text-muted-foreground text-[11px] uppercase tracking-[0.18em]">
              Error details
            </p>
            <dl className="mt-3 space-y-3">
              {details.map((detail) => (
                <div className="min-w-0" key={detail.label}>
                  <dt className="font-medium text-muted-foreground text-xs">{detail.label}</dt>
                  <dd className="mt-1 whitespace-pre-wrap break-words font-mono text-foreground text-xs leading-5">
                    {detail.value}
                  </dd>
                </div>
              ))}
            </dl>
          </div>
        )}
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
  readonly reset?: ErrorComponentProps<unknown>["reset"];
} & Omit<ErrorComponentProps<unknown>, "reset">;

export const AppErrorPage = ({ error, reset }: AppErrorPageProps) => {
  const retry = reset ?? reloadPage;

  return (
    <StatusPage
      code="500"
      description="The admin UI hit an unexpected error while rendering this page. The details below show the failure that reached the route boundary."
      details={getErrorDetails(error)}
      title="Something went wrong"
    >
      <button
        className={cn(actionClassName, "bg-primary text-primary-foreground")}
        onClick={retry}
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
};
