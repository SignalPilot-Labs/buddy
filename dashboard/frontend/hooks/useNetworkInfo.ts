"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchNetworkInfo } from "@/lib/api";
import { NETWORK_INFO_POLL_MS } from "@/lib/constants";

export function useNetworkInfo() {
  const [url, setUrl] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    const info = await fetchNetworkInfo();
    setUrl(info.url);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, NETWORK_INFO_POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return { url };
}
