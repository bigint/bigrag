import { BookOpen, Home, MessageCircle, RefreshCcw } from "lucide-react";
import type { ReactNode } from "react";

const actionClassName =
  "inline-flex h-10 items-center justify-center gap-2 rounded-md px-4 text-sm font-semibold focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fd-ring focus-visible:ring-offset-2 focus-visible:ring-offset-fd-background";

type StatusPageProps = {
  readonly code: string;
  readonly title: string;
  readonly description: string;
  readonly note?: string;
  readonly actions: ReactNode;
};

export const StatusPage = ({ actions, code, description, note, title }: StatusPageProps) => (
  <main className="flex min-h-dvh items-center justify-center bg-fd-background px-6 py-12 text-fd-foreground">
    <section className="w-full max-w-2xl rounded-xl border border-fd-border bg-fd-card p-6 sm:p-8">
      <div className="flex items-center justify-between gap-4">
        <a className="flex items-center gap-2 font-semibold tracking-tight" href="/">
          <span className="flex size-8 items-center justify-center rounded-md bg-fd-primary text-fd-primary-foreground">
            <span className="font-mono text-sm">bR</span>
          </span>
          bigRAG
        </a>
        <span className="rounded-md border border-fd-border bg-fd-muted px-2.5 py-1 font-mono text-fd-muted-foreground text-xs">
          {code}
        </span>
      </div>
      <div className="mt-14">
        <p className="font-mono text-fd-muted-foreground text-xs uppercase tracking-[0.2em]">
          Documentation
        </p>
        <h1 className="mt-3 max-w-xl text-4xl font-semibold tracking-normal sm:text-5xl">
          {title}
        </h1>
        <p className="mt-4 max-w-lg text-base text-fd-muted-foreground leading-7">{description}</p>
        {note && (
          <p className="mt-4 rounded-md border border-fd-border bg-fd-background px-3 py-2 font-mono text-fd-muted-foreground text-xs">
            {note}
          </p>
        )}
      </div>
      <div className="mt-7 flex flex-col gap-3 sm:flex-row">{actions}</div>
    </section>
  </main>
);

export const HomeAction = () => (
  <a className={`${actionClassName} bg-fd-primary text-fd-primary-foreground`} href="/">
    <Home className="size-4" />
    Home
  </a>
);

export const DocsAction = () => (
  <a className={`${actionClassName} border border-fd-border bg-fd-background`} href="/docs">
    <BookOpen className="size-4" />
    Docs
  </a>
);

type RetryActionProps = {
  readonly reset: () => void;
};

export const RetryAction = ({ reset }: RetryActionProps) => (
  <button
    className={`${actionClassName} bg-fd-primary text-fd-primary-foreground`}
    onClick={reset}
    type="button"
  >
    <RefreshCcw className="size-4" />
    Try again
  </button>
);

export const SupportAction = () => (
  <a
    className={`${actionClassName} border border-fd-border bg-fd-background`}
    href="mailto:yoginth@hey.com"
  >
    <MessageCircle className="size-4" />
    Support
  </a>
);
