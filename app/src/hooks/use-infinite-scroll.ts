import { type RefObject, useEffect } from "react";

interface UseInfiniteScrollOptions {
  readonly enabled: boolean;
  readonly onLoadMore: () => void;
  readonly rootMargin?: string;
}

export const useInfiniteScroll = (
  ref: RefObject<HTMLElement | null>,
  { enabled, onLoadMore, rootMargin = "320px 0px" }: UseInfiniteScrollOptions,
) => {
  useEffect(() => {
    const node = ref.current;
    if (!node || !enabled) return;
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry?.isIntersecting) onLoadMore();
      },
      { rootMargin },
    );
    observer.observe(node);
    return () => observer.disconnect();
  }, [ref, enabled, onLoadMore, rootMargin]);
};
