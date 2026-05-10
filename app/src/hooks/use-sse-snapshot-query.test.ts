import { useQuery, useQueryClient } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { useSseSnapshotQuery } from "./use-sse-snapshot-query";

const queryClient = {
  fetchQuery: vi.fn(),
  getQueryData: vi.fn(),
  setQueryData: vi.fn(),
};

const setStreaming = vi.fn();

class FakeEventSource {
  static instances: FakeEventSource[] = [];

  listeners = new Map<string, (event: unknown) => void>();
  onerror?: () => void;
  onopen?: () => void;
  close = vi.fn();

  constructor(
    public url: string,
    public init?: EventSourceInit,
  ) {
    FakeEventSource.instances.push(this);
  }

  addEventListener(type: string, listener: (event: unknown) => void) {
    this.listeners.set(type, listener);
  }
}

vi.mock("react", () => ({
  useEffect: vi.fn((fn: () => unknown) => fn()),
  useRef: vi.fn((value: unknown) => ({ current: value })),
  useState: vi.fn((value: unknown) => [value, setStreaming]),
}));

vi.mock("@tanstack/react-query", () => ({
  useQuery: vi.fn((options) => ({ data: "query-data", ...options })),
  useQueryClient: vi.fn(),
}));

beforeEach(() => {
  FakeEventSource.instances = [];
  vi.stubGlobal("EventSource", FakeEventSource);
  vi.mocked(useQueryClient).mockReturnValue(queryClient as never);
});

afterEach(() => {
  vi.clearAllMocks();
  vi.unstubAllGlobals();
});

describe("useSseSnapshotQuery", () => {
  it("streams snapshots into the query cache and closes on terminal payloads", () => {
    const queryFn = vi.fn();

    const result = useSseSnapshotQuery({
      closeWhen: (payload: { status: string }) => payload.status === "ready",
      path: "v1/admin/realtime/platform/stats",
      queryFn,
      queryKey: ["platform", "stats"],
    });

    const source = FakeEventSource.instances[0];
    expect(source.url).toBe("http://localhost:4000/v1/admin/realtime/platform/stats");
    expect(source.init).toEqual({ withCredentials: true });
    expect(useQuery).toHaveBeenCalledWith(
      expect.objectContaining({
        enabled: false,
        queryKey: ["platform", "stats"],
        retry: false,
      }),
    );
    expect(result).toMatchObject({ data: "query-data", streaming: false });

    source.onopen?.();
    expect(setStreaming).toHaveBeenCalledWith(true);

    source.listeners.get("snapshot")?.({
      data: JSON.stringify({
        generated_at: "2026-05-10T00:00:00Z",
        payload: { status: "ready" },
        topic: "stats",
      }),
    });

    expect(queryClient.setQueryData).toHaveBeenCalledWith(["platform", "stats"], {
      status: "ready",
    });
    expect(source.close).toHaveBeenCalled();
    expect(setStreaming).toHaveBeenLastCalledWith(false);
  });

  it("falls back to fetchQuery once when stream errors arrive before cached data", () => {
    queryClient.getQueryData.mockReturnValue(undefined);
    const queryFn = vi.fn();

    useSseSnapshotQuery({
      path: "v1/admin/realtime/backups",
      queryFn,
      queryKey: ["backups"],
    });

    const source = FakeEventSource.instances[0];
    source.listeners.get("error")?.({ data: "retry" });
    source.listeners.get("error")?.({ data: "retry" });
    source.onerror?.();

    expect(queryClient.fetchQuery).toHaveBeenCalledTimes(1);
    expect(queryClient.fetchQuery).toHaveBeenCalledWith({
      queryFn: expect.any(Function),
      queryKey: ["backups"],
    });
    expect(setStreaming).toHaveBeenCalledWith(false);
  });

  it("disables streaming without opening an EventSource", () => {
    useSseSnapshotQuery({
      enabled: false,
      path: "v1/admin/realtime/backups",
      queryFn: vi.fn(),
      queryKey: ["backups"],
    });

    expect(FakeEventSource.instances).toEqual([]);
    expect(setStreaming).toHaveBeenCalledWith(false);
  });
});
