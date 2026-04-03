"use client";

import { useState, useEffect, useCallback } from "react";
import type { Run } from "@/lib/types";
import { fetchRuns } from "@/lib/api";

export function useRuns(repo?: string | null, pollInterval = 8000) {
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const data = await fetchRuns(repo || undefined);
      setRuns(data);
    } catch (err) {
      console.warn("Failed to fetch runs, will retry:", err);
    } finally {
      setLoading(false);
    }
  }, [repo]);

  useEffect(() => {
    setLoading(true);
    refresh();
    const id = setInterval(refresh, pollInterval);
    return () => clearInterval(id);
  }, [refresh, pollInterval]);

  return { runs, loading, refresh };
}
