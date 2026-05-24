import {
  hashKey,
  type QueryClient,
  type QueryFunction,
  type QueryKey,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import {
  type RealtimeSnapshotSubscription,
  useRealtimeSnapshotSubscriptions,
} from "@/hooks/use-realtime-subscriptions";
import {
  closeAllRealtimeStreams,
  compactParams,
  DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  DEFAULT_POLL_INTERVAL_MS,
  type ErrorKind,
  MAX_RECONNECT_ATTEMPTS,
  type RealtimeMessage,
  type RealtimeParams,
  type SnapshotEvent,
  subscribeStream,
} from "@/lib/realtime-socket";

export type { RealtimeParams, RealtimeSnapshotSubscription };
export { closeAllRealtimeStreams, useRealtimeSnapshotSubscriptions };

type RealtimeSnapshotQueryOptions<T> = {
  closeWhen?: (payload: T) => boolean;
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  params?: RealtimeParams;
  pollIntervalMs?: number;
  queryFn: QueryFunction<T, QueryKey>;
  queryKey: QueryKey;
  topic: string;
};

const jitterInterval = (ms: number) => Math.round(ms * (0.85 + Math.random() * 0.3));

export const useRealtimeSnapshotQuery = <T>({
  closeWhen,
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  params,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  queryFn,
  queryKey,
  topic,
}: RealtimeSnapshotQueryOptions<T>) => {
  const queryClient = useQueryClient();
  const queryClientRef = useRef<QueryClient>(queryClient);
  const closeWhenRef = useRef(closeWhen);
  const queryFnRef = useRef(queryFn);
  const fallbackStartedRef = useRef(false);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const queryKeyHash = useMemo(() => hashKey(queryKey), [queryKey]);
  const queryKeyRef = useRef(queryKey);
  const paramsHash = useMemo(() => JSON.stringify(compactParams(params)), [params]);

  useEffect(() => {
    queryClientRef.current = queryClient;
  }, [queryClient]);

  useEffect(() => {
    closeWhenRef.current = closeWhen;
  }, [closeWhen]);

  useEffect(() => {
    queryFnRef.current = queryFn;
  }, [queryFn]);

  useEffect(() => {
    queryKeyRef.current = queryKey;
  }, [queryKey]);

  const query = useQuery<T>({
    enabled,
    queryFn: (context) => queryFnRef.current(context),
    queryKey,
    refetchInterval: (q) => {
      if (q.state.data != null && closeWhenRef.current?.(q.state.data as T)) return false;
      return realtimeUnavailable ? jitterInterval(pollIntervalMs) : false;
    },
    retry: false,
  });

  useEffect(() => {
    void queryKeyHash;
    if (!enabled) {
      setStreaming(false);
      setRealtimeUnavailable(false);
      return;
    }

    fallbackStartedRef.current = false;
    setRealtimeUnavailable(false);
    setStreaming(true);

    let sawSnapshot = false;
    let unsubscribed = false;
    let failureCount = 0;

    const fetchFallback = () => {
      if (fallbackStartedRef.current) return;
      fallbackStartedRef.current = true;
      setRealtimeUnavailable(true);
      void queryClientRef.current.invalidateQueries({ queryKey: queryKeyRef.current });
    };

    const firstSnapshotTimer = window.setTimeout(() => {
      if (!sawSnapshot) fetchFallback();
    }, firstSnapshotTimeoutMs);

    const handleMessage = (message: RealtimeMessage<unknown>) => {
      if (message.type === "complete") {
        setStreaming(false);
        return;
      }
      if (message.type !== "snapshot") return;
      const snapshot = message as SnapshotEvent<T>;
      sawSnapshot = true;
      failureCount = 0;
      setRealtimeUnavailable(false);
      fallbackStartedRef.current = false;
      queryClientRef.current.setQueryData(queryKeyRef.current, snapshot.payload);
      if (snapshot.payload != null && closeWhenRef.current?.(snapshot.payload)) {
        unsubscribe();
        unsubscribed = true;
        setStreaming(false);
      }
    };

    const handleError = (kind: ErrorKind) => {
      if (kind === "transport") {
        fetchFallback();
        return;
      }
      failureCount += 1;
      if (failureCount >= MAX_RECONNECT_ATTEMPTS) {
        fetchFallback();
        setStreaming(false);
      }
    };

    const unsubscribe = subscribeStream(
      topic,
      JSON.parse(paramsHash) as RealtimeParams,
      handleMessage,
      handleError,
    );

    return () => {
      window.clearTimeout(firstSnapshotTimer);
      if (!unsubscribed) unsubscribe();
      setStreaming(false);
    };
  }, [enabled, firstSnapshotTimeoutMs, paramsHash, queryKeyHash, topic]);

  return { ...query, realtimeUnavailable, streaming };
};
