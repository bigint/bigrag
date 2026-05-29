import { match } from "ts-pattern";

export const API_KEY_UNSCOPED = "__all__";

export type ApiKeyFormValues = {
  accessLevel: "full" | "read" | "write" | "custom";
  collection: string;
  customExpiresAt: string;
  expiresPreset: "never" | "7d" | "30d" | "90d" | "custom";
  name: string;
  scopesText: string;
};

export const defaultApiKeyFormValues = (): ApiKeyFormValues => ({
  accessLevel: "full",
  collection: API_KEY_UNSCOPED,
  customExpiresAt: "",
  expiresPreset: "never",
  name: "",
  scopesText: "",
});

export const validateApiKeyFormValues = ({
  accessLevel,
  customExpiresAt,
  expiresPreset,
  name,
  scopesText,
}: ApiKeyFormValues): string | undefined => {
  if (!name.trim()) return "Name is required";
  if (accessLevel === "custom" && parseScopes(scopesText).length === 0) {
    return "Custom access needs at least one scope";
  }
  if (expiresPreset === "custom" && !customExpiresAt) {
    return "Custom expiration needs a date";
  }
  return undefined;
};

export const apiKeyBodyFromValues = (values: ApiKeyFormValues) => ({
  collection: values.collection === API_KEY_UNSCOPED ? null : values.collection,
  expires_at: expirationFromPreset(values),
  name: values.name.trim(),
  scopes: scopesFromAccessLevel(values),
});

const scopesFromAccessLevel = ({ accessLevel, scopesText }: ApiKeyFormValues) => {
  return match(accessLevel)
    .with("full", () => ["*:*"])
    .with("read", () => ["collection:read", "document:read", "query:read", "chat:read"])
    .with("write", () => [
      "collection:read",
      "document:read",
      "document:upload",
      "query:read",
      "chat:write",
    ])
    .with("custom", () => parseScopes(scopesText))
    .exhaustive();
};

const parseScopes = (value: string) =>
  value
    .split(/[\n,]/)
    .map((scope) => scope.trim())
    .filter(Boolean);

const expirationFromPreset = ({ customExpiresAt, expiresPreset }: ApiKeyFormValues) => {
  return match(expiresPreset)
    .with("never", () => null)
    .with("custom", () => (customExpiresAt ? new Date(customExpiresAt).toISOString() : null))
    .otherwise((preset) => {
      const days = Number.parseInt(preset, 10);
      const expires = new Date();
      expires.setDate(expires.getDate() + days);
      return expires.toISOString();
    });
};
