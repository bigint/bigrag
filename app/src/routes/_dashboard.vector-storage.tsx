import { createFileRoute, useNavigate } from "@tanstack/react-router";
import {
  VectorStoragePage,
  type VectorStorageProvider,
} from "@/features/vector-storage/vector-storage-page";

type VectorStorageSearch = {
  provider?: string;
};

export const Route = createFileRoute("/_dashboard/vector-storage")({
  validateSearch: (search: Record<string, unknown>): VectorStorageSearch => ({
    provider: typeof search.provider === "string" ? search.provider : undefined,
  }),
  component: () => <VectorStorageRoute />,
});

const VectorStorageRoute = () => {
  const navigate = useNavigate();
  const search = Route.useSearch();

  const setProvider = (provider: VectorStorageProvider) =>
    navigate({
      to: "/vector-storage",
      search: { provider },
      replace: true,
    });

  return <VectorStoragePage onProviderChange={setProvider} provider={search.provider} />;
};
