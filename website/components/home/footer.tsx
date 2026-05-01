export function Footer() {
  return (
    <footer className="border-t border-fd-border">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 py-8 text-sm text-fd-muted-foreground sm:flex-row">
        <p>
          Built by{" "}
          <a
            className="font-medium text-fd-foreground hover:text-fd-foreground/80"
            href="https://x.com/yoginth"
            rel="noopener noreferrer"
            target="_blank"
          >
            Yoginth
          </a>
        </p>
        <div className="flex items-center gap-6">
          <a
            className="hover:text-fd-foreground"
            href="https://github.com/bigint/bigrag"
            rel="noopener noreferrer"
            target="_blank"
          >
            GitHub
          </a>
          <a
            className="hover:text-fd-foreground"
            href="https://x.com/yoginth"
            rel="noopener noreferrer"
            target="_blank"
          >
            X
          </a>
          <a className="hover:text-fd-foreground" href="mailto:yoginth@hey.com">
            Support
          </a>
        </div>
      </div>
    </footer>
  );
}
