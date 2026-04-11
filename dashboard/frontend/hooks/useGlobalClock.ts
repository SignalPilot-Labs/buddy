"use client";

import { useSyncExternalStore } from "react";
import { GLOBAL_CLOCK_INTERVAL_MS } from "@/lib/constants";

// Module-level store: single interval shared by all subscribers.
let _now = Date.now();
let _intervalId: ReturnType<typeof setInterval> | null = null;
let _subscriberCount = 0;
const _listeners = new Set<() => void>();

function _tick(): void {
  _now = Date.now();
  for (const listener of _listeners) {
    listener();
  }
}

function _subscribe(listener: () => void): () => void {
  _listeners.add(listener);
  _subscriberCount++;
  if (_subscriberCount === 1) {
    _intervalId = setInterval(_tick, GLOBAL_CLOCK_INTERVAL_MS);
  }
  return () => {
    _listeners.delete(listener);
    _subscriberCount--;
    if (_subscriberCount === 0 && _intervalId !== null) {
      clearInterval(_intervalId);
      _intervalId = null;
    }
  };
}

function _getSnapshot(): number {
  return _now;
}

export function useGlobalClock(): number {
  return useSyncExternalStore(_subscribe, _getSnapshot, _getSnapshot);
}
