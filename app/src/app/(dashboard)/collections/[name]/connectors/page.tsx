"use client";

import { useRouter } from "next/navigation";
import { use, useEffect } from "react";
import { Spinner } from "@/components/ui/spinner";

const ConnectorsIndex = ({ params }: { params: Promise<{ name: string }> }) => {
  const { name } = use(params);
  const router = useRouter();

  useEffect(() => {
    router.replace(`/collections/${name}/connectors/google-drive`);
  }, [name, router]);

  return (
    <div className="flex justify-center py-12">
      <Spinner />
    </div>
  );
};

export default ConnectorsIndex;
