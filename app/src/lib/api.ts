import ky, { HTTPError, type KyInstance } from "ky";

const api: KyInstance = ky.create({
  prefix: "/api/bigrag",
  credentials: "include",
  timeout: 120_000,
  retry: { limit: 1, methods: ["get", "head"] },
  hooks: {
    beforeError: [
      async ({ error }) => {
        if (error instanceof HTTPError) {
          try {
            const body = (await error.response.clone().json()) as { detail?: string };
            if (body.detail) {
              const wrapped = new Error(body.detail) as Error & { status?: number };
              wrapped.name = "HTTPError";
              wrapped.status = error.response.status;
              return wrapped;
            }
          } catch {}
        }
        return error;
      },
    ],
  },
});

export const apiClient = {
  get: <T>(path: string, searchParams?: Record<string, string | number | boolean>) =>
    api.get(path, searchParams ? { searchParams } : undefined).json<T>(),
  post: <T>(path: string, body?: unknown) =>
    api.post(path, body === undefined ? undefined : { json: body }).json<T>(),
  put: <T>(path: string, body?: unknown) =>
    api.put(path, body === undefined ? undefined : { json: body }).json<T>(),
  patch: <T>(path: string, body?: unknown) =>
    api.patch(path, body === undefined ? undefined : { json: body }).json<T>(),
  delete: <T>(path: string) => api.delete(path).json<T>(),
  postForm: <T>(path: string, form: FormData) => api.post(path, { body: form }).json<T>(),
  raw: api,
};
