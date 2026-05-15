import type { GoogleConnectorConfig } from "@/types/bigrag";

export type GoogleConnectorFormValues = {
  clientId: string;
  clientSecret: string;
  enabled: boolean;
};

export const defaultGoogleConnectorFormValues = (
  config?: GoogleConnectorConfig,
): GoogleConnectorFormValues => ({
  clientId: config?.client_id ?? "",
  clientSecret: "",
  enabled: config?.enabled ?? true,
});

export const validateGoogleConnectorFormValues = ({
  clientId,
  enabled,
}: GoogleConnectorFormValues): string | undefined =>
  enabled && !clientId.trim() ? "OAuth client ID is required when enabled" : undefined;

export const googleConnectorPayload = ({
  clientId,
  clientSecret,
  enabled,
}: GoogleConnectorFormValues) => ({
  client_id: clientId.trim(),
  client_secret: clientSecret.trim() || null,
  enabled,
});
