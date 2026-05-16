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
  if (accessLevel === "full") return null;
  if (accessLevel === "read") {
    return ["collection:read", "document:read", "query:read", "chat:read"];
  }
  if (accessLevel === "write") {
    return ["collection:read", "document:read", "document:upload", "query:read", "chat:write"];
  }
  return parseScopes(scopesText);
};

const parseScopes = (value: string) =>
  value
    .split(/[\n,]/)
    .map((scope) => scope.trim())
    .filter(Boolean);

const expirationFromPreset = ({ customExpiresAt, expiresPreset }: ApiKeyFormValues) => {
  if (expiresPreset === "never") return null;
  if (expiresPreset === "custom") return customExpiresAt ? new Date(customExpiresAt).toISOString() : null;
  const days = Number.parseInt(expiresPreset, 10);
  const expires = new Date();
  expires.setDate(expires.getDate() + days);
  return expires.toISOString();
};
