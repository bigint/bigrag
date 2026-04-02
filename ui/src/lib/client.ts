import { BigRAG } from "@bigrag/client";
import { getBaseUrl, getSessionToken } from "./auth-store";

export const getClient = () =>
  new BigRAG({
    apiKey: getSessionToken(),
    baseUrl: getBaseUrl(),
  });
