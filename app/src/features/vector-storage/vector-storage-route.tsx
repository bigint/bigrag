import { getRouteApi, useNavigate } from "@tanstack/react-router";
import {
  VectorStoragePage,
  type VectorStorageProvider,
} from "@/features/vector-storage/vector-storage-page";

const routeApi = getRouteApi("/_dashboard/vector-storage");

export const VectorStorageRoute = () => {
  const navigate = useNavigate();
  const search = routeApi.useSearch();

  const setProvider = (provider: VectorStorageProvider) =>
    navigate({
      to: "/vector-storage",
      search: { provider },
      replace: true,
    });

  return <VectorStoragePage onProviderChange={setProvider} provider={search.provider} />;
};
