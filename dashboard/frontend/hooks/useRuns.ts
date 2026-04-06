"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import type { Run } from "@/lib/types";
import { fetchRuns } from "@/lib/api";

export function useRuns(repo?: string | null, pollInterval = 8000) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<boolean>(false);
  const genRef = useRef(0);

  const refresh = useCallback(async () => {
    const gen = ++genRef.current;
    try {
      const data = await fetchRuns(repo || undefined);
      // Discard stale results if repo filter changed during fetch
      if (gen !== genRef.current) return;
      setRuns(data);
      setFetchError(false);
    } catch (err) {
      console.warn("Failed to fetch runs, will retry:", err);
      if (gen === genRef.current) setFetchError(true);
    } finally {
      if (gen === genRef.current) setLoading(false);
    }
  }, [repo]);

  useEffect(() => {
    setLoading(true);
    refresh();
    const id = setInterval(refresh, pollInterval);
    return () => clearInterval(id);
  }, [refresh, pollInterval]);

  return { runs, loading, refresh, fetchError };
}
