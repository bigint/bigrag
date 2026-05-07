import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";

export const Route = createFileRoute("/_dashboard/collections/$name/")({
  component: () => <CollectionIndex />,
});

const CollectionIndex = () => {
  const { name } = Route.useParams();
  const navigate = useNavigate();

  useEffect(() => {
    navigate({
      to: "/collections/$name/documents",
      params: { name },
      replace: true,
    });
  }, [name, navigate]);

  return (
    <div className="flex justify-center py-12">
      <Spinner />
    </div>
  );
};
