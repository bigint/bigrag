export const API_KEY_UNSCOPED = "__all__";

export type ApiKeyFormValues = {
  collection: string;
  name: string;
};

export const defaultApiKeyFormValues = (): ApiKeyFormValues => ({
  collection: API_KEY_UNSCOPED,
  name: "",
});

export const validateApiKeyFormValues = ({ name }: ApiKeyFormValues): string | undefined =>
  name.trim() ? undefined : "Name is required";

export const apiKeyBodyFromValues = ({ collection, name }: ApiKeyFormValues) => ({
  collection: collection === API_KEY_UNSCOPED ? null : collection,
  name,
});
