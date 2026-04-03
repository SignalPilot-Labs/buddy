"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import {
  fetchTunnelStatus,
  startTunnel as apiStart,
  stopTunnel as apiStop,
} from "@/lib/api";
import type { TunnelStatus } from "@/lib/api";

const POLL_INTERVAL = 10_000;
const RAPID_POLLS = [1000, 3000, 5000];

export function useTunnel() {
  const [status, setStatus] = useState<TunnelStatus["status"]>("not_found");
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const rapidTimers = useRef<ReturnType<typeof setTimeout>[]>([]);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchTunnelStatus();
      setStatus(data.status);
      setUrl(data.url ?? null);
    } catch {
      setStatus("error");
      setUrl(null);
    }
  }, []);

  const rapidRefresh = useCallback(() => {
    rapidTimers.current.forEach(clearTimeout);
    rapidTimers.current = RAPID_POLLS.map((ms) =>
      setTimeout(() => refresh(), ms),
    );
  }, [refresh]);

  const start = useCallback(async () => {
    try {
      setLoading(true);
      await apiStart();
      setStatus("running");
      rapidRefresh();
    } finally {
      setLoading(false);
    }
  }, [rapidRefresh]);

  const stop = useCallback(async () => {
    try {
      setLoading(true);
      await apiStop();
      setStatus("exited");
      setUrl(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL);
    return () => {
      clearInterval(id);
      rapidTimers.current.forEach(clearTimeout);
    };
  }, [refresh]);

  return { status, url, loading, start, stop, refresh };
}
