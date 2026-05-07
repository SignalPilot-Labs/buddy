"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { fetchNetworkInfo } from "@/lib/api";
import { NETWORK_INFO_POLL_MS } from "@/lib/constants";

export function useNetworkInfo() {
  const [url, setUrl] = useState<string | null>(null);
  const genRef = useRef(0);

  const refresh = useCallback(async () => {
    const gen = ++genRef.current;
    const info = await fetchNetworkInfo();
    if (gen !== genRef.current) return;
    setUrl(info.url);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, NETWORK_INFO_POLL_MS);
    return () => clearInterval(id);
  }, [refresh]);

  return { url };
}
