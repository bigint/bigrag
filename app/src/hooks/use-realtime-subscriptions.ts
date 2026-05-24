import { useEffect, useMemo, useRef, useState } from "react";
import {
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

export type RealtimeSnapshotSubscription = {
  key: string;
  params?: RealtimeParams;
  topic: string;
};

type RealtimeSnapshotSubscriptionsOptions<T> = {
  enabled?: boolean;
  firstSnapshotTimeoutMs?: number;
  onSnapshot: (payload: T, subscription: RealtimeSnapshotSubscription) => void;
  onUnavailable?: (subscription: RealtimeSnapshotSubscription) => void;
  pollIntervalMs?: number;
  subscriptions: RealtimeSnapshotSubscription[];
};

export const useRealtimeSnapshotSubscriptions = <T>({
  enabled = true,
  firstSnapshotTimeoutMs = DEFAULT_FIRST_SNAPSHOT_TIMEOUT_MS,
  onSnapshot,
  onUnavailable,
  pollIntervalMs = DEFAULT_POLL_INTERVAL_MS,
  subscriptions,
}: RealtimeSnapshotSubscriptionsOptions<T>) => {
  const onSnapshotRef = useRef(onSnapshot);
  const onUnavailableRef = useRef(onUnavailable);
  const [realtimeUnavailable, setRealtimeUnavailable] = useState(false);
  const [streaming, setStreaming] = useState(false);
  const normalizedSubscriptions = useMemo(
    () =>
      subscriptions.map((subscription) => ({
        ...subscription,
        params: compactParams(subscription.params),
      })),
    [subscriptions],
  );
  const subscriptionsHash = useMemo(
    () => JSON.stringify(normalizedSubscriptions),
    [normalizedSubscriptions],
  );

  useEffect(() => {
    onSnapshotRef.current = onSnapshot;
  }, [onSnapshot]);

  useEffect(() => {
    onUnavailableRef.current = onUnavailable;
  }, [onUnavailable]);

  useEffect(() => {
    const activeSubscriptions = JSON.parse(subscriptionsHash) as RealtimeSnapshotSubscription[];
    if (!enabled || activeSubscriptions.length === 0) {
      setStreaming(false);
      setRealtimeUnavailable(false);
      return;
    }

    setRealtimeUnavailable(false);
    setStreaming(true);

    const activeKeys = new Set(activeSubscriptions.map((subscription) => subscription.key));
    const fallbackKeys = new Set<string>();
    const failureCounts = new Map<string, number>();
    const pollTimers = new Map<string, number>();
    const snapshotKeys = new Set<string>();
    const timers: number[] = [];
    const unsubscribes: (() => void)[] = [];

    const clearPoll = (key: string) => {
      const timer = pollTimers.get(key);
      if (timer === undefined) return;
      window.clearInterval(timer);
      pollTimers.delete(key);
    };

    const markComplete = (key: string) => {
      activeKeys.delete(key);
      clearPoll(key);
      if (activeKeys.size === 0) setStreaming(false);
    };

    const fallback = (subscription: RealtimeSnapshotSubscription) => {
      if (fallbackKeys.has(subscription.key)) return;
      fallbackKeys.add(subscription.key);
      setRealtimeUnavailable(true);
      onUnavailableRef.current?.(subscription);
      if (pollIntervalMs > 0) {
        pollTimers.set(
          subscription.key,
          window.setInterval(() => onUnavailableRef.current?.(subscription), pollIntervalMs),
        );
      }
    };

    for (const subscription of activeSubscriptions) {
      const timer = window.setTimeout(() => {
        if (!snapshotKeys.has(subscription.key)) fallback(subscription);
      }, firstSnapshotTimeoutMs);
      timers.push(timer);

      const handleMessage = (message: RealtimeMessage<unknown>) => {
        if (message.type === "complete") {
          markComplete(subscription.key);
          return;
        }
        if (message.type !== "snapshot") return;
        const snapshot = message as SnapshotEvent<T>;
        snapshotKeys.add(subscription.key);
        failureCounts.set(subscription.key, 0);
        fallbackKeys.delete(subscription.key);
        clearPoll(subscription.key);
        if (fallbackKeys.size === 0) setRealtimeUnavailable(false);
        onSnapshotRef.current(snapshot.payload, subscription);
      };

      const handleError = (kind: ErrorKind) => {
        if (kind === "transport") {
          fallback(subscription);
          return;
        }
        const failureCount = (failureCounts.get(subscription.key) ?? 0) + 1;
        failureCounts.set(subscription.key, failureCount);
        if (failureCount >= MAX_RECONNECT_ATTEMPTS) {
          fallback(subscription);
          markComplete(subscription.key);
        }
      };

      unsubscribes.push(
        subscribeStream(subscription.topic, subscription.params, handleMessage, handleError),
      );
    }

    return () => {
      for (const timer of timers) window.clearTimeout(timer);
      for (const timer of pollTimers.values()) window.clearInterval(timer);
      for (const unsubscribe of unsubscribes) unsubscribe();
      setStreaming(false);
    };
  }, [enabled, firstSnapshotTimeoutMs, pollIntervalMs, subscriptionsHash]);

  return { realtimeUnavailable, streaming };
};
