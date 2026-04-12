"use client";

import { useState, useEffect } from "react";

// Module-level singleton: one shared interval for all active subscribers.
let subscribers: Set<() => void> = new Set();
let intervalId: ReturnType<typeof setInterval> | null = null;

const TICK_INTERVAL_MS = 1000;

function startInterval(): void {
  if (intervalId !== null) return;
  intervalId = setInterval(() => {
    subscribers.forEach((fn) => fn());
  }, TICK_INTERVAL_MS);
}

function stopInterval(): void {
  if (intervalId === null) return;
  clearInterval(intervalId);
  intervalId = null;
}

/**
 * Returns a `Date.now()` timestamp that updates every second.
 * When `active` is false, the hook does not subscribe and returns a stable value.
 * Uses a module-level singleton interval so N concurrent callers share one timer.
 */
export function useNow(active: boolean): number {
  const [now, setNow] = useState<number>(Date.now);

  useEffect(() => {
    if (!active) return;

    const tick = () => setNow(Date.now());
    subscribers.add(tick);
    if (subscribers.size === 1) startInterval();

    return () => {
      subscribers.delete(tick);
      if (subscribers.size === 0) stopInterval();
    };
  }, [active]);

  return now;
}
