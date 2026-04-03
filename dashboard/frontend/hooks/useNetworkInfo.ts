"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchNetworkInfo } from "@/lib/api";

const POLL_INTERVAL = 30_000;

export function useNetworkInfo() {
  const [url, setUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const info = await fetchNetworkInfo();
    setUrl(info.url);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [refresh]);

  return { url };
}
