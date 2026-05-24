import { useState } from "react";
import { toast } from "sonner";
import { bigragApiUrl } from "@/config/runtime";

interface VerifyMessages {
  readonly successMessage: string;
  readonly errorMessage: string;
}

export const useVerifyCredential = () => {
  const [verifying, setVerifying] = useState(false);

  const verify = async (token: string, { successMessage, errorMessage }: VerifyMessages) => {
    setVerifying(true);
    try {
      const response = await fetch(`${bigragApiUrl}/v1/auth/whoami`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) throw new Error(await response.text());
      toast.success(successMessage);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : errorMessage);
    } finally {
      setVerifying(false);
    }
  };

  return { verifying, verify };
};
