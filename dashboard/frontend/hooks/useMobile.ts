"use client";

import { useSyncExternalStore } from "react";

const MOBILE_BREAKPOINT = 640;

function subscribe(callback: () => void): () => void {
  const mq = window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`);
  mq.addEventListener("change", callback);
  return () => mq.removeEventListener("change", callback);
}

function getSnapshot(): boolean {
  return window.matchMedia(`(max-width: ${MOBILE_BREAKPOINT}px)`).matches;
}

function getServerSnapshot(): boolean {
  return false;
}

export function useMobile(): boolean {
  return useSyncExternalStore(subscribe, getSnapshot, getServerSnapshot);
}
