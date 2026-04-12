"use client";

import { useRouter } from "next/navigation";
import { use, useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";

const CollectionIndex = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name } = use(params);
  const router = useRouter();
  useEffect(() => {
    router.replace(`/collections/${name}/documents`);
  }, [name, router]);
  return (
    <div className="flex justify-center py-12">
      <Spinner />
    </div>
  );
};

export default CollectionIndex;
