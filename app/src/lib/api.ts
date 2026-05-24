import { errorForStatus } from "@bigrag/client";
import ky, { HTTPError, type KyInstance, type Options } from "ky";
import { bigragApiUrl } from "@/config/runtime";

type SearchParams = Record<string, string | number | boolean | null | undefined>;

export type ApiRequestOptions = {
  searchParams?: SearchParams;
  signal?: AbortSignal;
  timeoutMs?: number;
};

const API_TIMEOUT_MS = 20_000;
export const AUTH_TIMEOUT_MS = 6_000;
const LONG_REQUEST_TIMEOUT_MS = 120_000;
export const SEARCH_TIMEOUT_MS = 30_000;

const api: KyInstance = ky.create({
  prefix: bigragApiUrl,
  credentials: "include",
  timeout: API_TIMEOUT_MS,
  retry: { limit: 1, methods: ["get", "head"] },
});

const idempotencyHeaders = (): Record<string, string> => ({
  "Idempotency-Key": crypto.randomUUID(),
});

const toTypedError = async (error: unknown): Promise<never> => {
  if (error instanceof HTTPError) {
    let message = error.message;
    try {
      const body = (await error.response.clone().json()) as { detail?: string };
      if (body.detail) {
        message = body.detail;
      }
    } catch {}
    throw errorForStatus(error.response.status, message);
  }
  throw error;
};

const isRequestOptions = (
  value: SearchParams | ApiRequestOptions | undefined,
): value is ApiRequestOptions =>
  Boolean(
    value &&
      ("searchParams" in value || "signal" in value || "timeoutMs" in value || "timeout" in value),
  );

const compactSearchParams = (
  searchParams: SearchParams | undefined,
): Record<string, string | number | boolean> | undefined =>
  searchParams
    ? (Object.fromEntries(
        Object.entries(searchParams).filter(([, value]) => value !== undefined && value !== null),
      ) as Record<string, string | number | boolean>)
    : undefined;

const requestOptions = (options?: ApiRequestOptions): Options => ({
  ...(options?.signal ? { signal: options.signal } : {}),
  ...(options?.timeoutMs ? { timeout: options.timeoutMs } : {}),
  ...(options?.searchParams ? { searchParams: compactSearchParams(options.searchParams) } : {}),
});

const normalizeGetOptions = (
  value?: SearchParams | ApiRequestOptions,
): ApiRequestOptions | undefined =>
  isRequestOptions(value) ? value : value ? { searchParams: value } : undefined;

export const apiClient = {
  get: <T>(path: string, searchParamsOrOptions?: SearchParams | ApiRequestOptions) =>
    api
      .get(path, requestOptions(normalizeGetOptions(searchParamsOrOptions)))
      .json<T>()
      .catch(toTypedError),
  post: <T>(path: string, body?: unknown, options?: ApiRequestOptions) =>
    api
      .post(path, {
        ...requestOptions(options),
        headers: idempotencyHeaders(),
        ...(body === undefined ? {} : { json: body }),
      })
      .json<T>()
      .catch(toTypedError),
  put: <T>(path: string, body?: unknown, options?: ApiRequestOptions) =>
    api
      .put(path, {
        ...requestOptions(options),
        headers: idempotencyHeaders(),
        ...(body === undefined ? {} : { json: body }),
      })
      .json<T>()
      .catch(toTypedError),
  patch: <T>(path: string, body?: unknown, options?: ApiRequestOptions) =>
    api
      .patch(path, {
        ...requestOptions(options),
        headers: idempotencyHeaders(),
        ...(body === undefined ? {} : { json: body }),
      })
      .json<T>()
      .catch(toTypedError),
  delete: <T>(path: string, options?: ApiRequestOptions) =>
    api
      .delete(path, { ...requestOptions(options), headers: idempotencyHeaders() })
      .json<T>()
      .catch(toTypedError),
  postForm: <T>(path: string, form: FormData, options?: ApiRequestOptions) =>
    api
      .post(path, {
        ...requestOptions({ timeoutMs: LONG_REQUEST_TIMEOUT_MS, ...options }),
        headers: idempotencyHeaders(),
        body: form,
      })
      .json<T>()
      .catch(toTypedError),
};
