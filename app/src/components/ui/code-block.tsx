import { CopyButton } from "@/components/ui/copy-button";

export const CodeBlock = ({ code, label }: { code: string; label: string }) => (
  <div className="relative">
    <pre className="overflow-x-auto rounded-md border border-border bg-muted/50 p-4 font-mono text-xs leading-relaxed">
      <code>{code}</code>
    </pre>
    <div className="absolute top-2 right-2">
      <CopyButton code={code} label={label} />
    </div>
  </div>
);
