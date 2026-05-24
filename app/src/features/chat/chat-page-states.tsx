import { Link } from "@tanstack/react-router";
import { BookOpen, Clock3, FileText, type LucideIcon, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Spinner } from "@/components/ui/spinner";

export const LoadingState = ({ label = "Loading chat" }: { label?: string }) => (
  <div className="flex flex-1 items-center justify-center">
    <div className="flex items-center gap-3 rounded-2xl border border-border bg-background px-4 py-3 text-sm font-semibold">
      <Spinner />
      {label}
    </div>
  </div>
);

export const NoCollectionsState = () => (
  <div className="flex flex-1 items-center justify-center px-4 py-8">
    <div className="w-full max-w-xl rounded-xl border border-border bg-background p-6 text-center">
      <div className="mx-auto mb-4 flex size-12 items-center justify-center rounded-2xl border border-border bg-muted">
        <BookOpen className="size-6 text-muted-foreground" />
      </div>
      <h2 className="text-lg font-semibold">No collections available</h2>
      <p className="mx-auto mt-2 max-w-sm text-sm leading-6 text-muted-foreground">
        Create or ingest a collection first. Chat needs indexed documents before it can retrieve
        evidence.
      </p>
      <div className="mt-5">
        <Link to="/collections">
          <Button>
            <FileText className="size-4" />
            Open collections
          </Button>
        </Link>
      </div>
      <div className="mt-5 grid grid-cols-3 gap-2 text-xs text-muted-foreground">
        <NoCollectionMetric icon={BookOpen} label="Create" />
        <NoCollectionMetric icon={Clock3} label="Ingest" />
        <NoCollectionMetric icon={Search} label="Query" />
      </div>
    </div>
  </div>
);

const NoCollectionMetric = ({ icon: Icon, label }: { icon: LucideIcon; label: string }) => (
  <div className="rounded-2xl border border-border bg-muted/40 px-2 py-2">
    <Icon className="mx-auto mb-1 size-3.5" />
    {label}
  </div>
);
