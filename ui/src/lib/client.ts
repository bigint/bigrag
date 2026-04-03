import { BigRAG } from "@bigrag/client";
import { getBaseUrl, getSessionToken } from "./auth-store";

let _cachedClient: BigRAG | null = null;
let _cachedToken: string | null = null;
let _cachedUrl: string | null = null;

export const getClient = () => {
  const token = getSessionToken();
  const url = getBaseUrl();

  if (_cachedClient && _cachedToken === token && _cachedUrl === url) {
    return _cachedClient;
  }

  _cachedClient = new BigRAG({ apiKey: token, baseUrl: url });
  _cachedToken = token;
  _cachedUrl = url;
  return _cachedClient;
};

export const clearClientCache = () => {
  _cachedClient = null;
};
