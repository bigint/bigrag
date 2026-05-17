import { createFileRoute, lazyRouteComponent } from "@tanstack/react-router";

type VectorStorageSearch = {
  provider?: string;
};

export const Route = createFileRoute("/_dashboard/vector-storage")({
  validateSearch: (search: Record<string, unknown>): VectorStorageSearch => ({
    provider: typeof search.provider === "string" ? search.provider : undefined,
  }),
  component: lazyRouteComponent(() =>
    import("@/features/vector-storage/vector-storage-route").then((m) => ({
      default: m.VectorStorageRoute,
    })),
  ),
});
