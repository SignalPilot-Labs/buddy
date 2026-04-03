"use client";

import { useState, useEffect, useCallback } from "react";
import { fetchTunnelInfo } from "@/lib/api";

const POLL_INTERVAL = 10_000;

export function useTunnel() {
  const [url, setUrl] = useState<string | null>(null);
  const [token, setToken] = useState<string | null>(null);
  const [visible, setVisible] = useState(false);

  const refresh = useCallback(async () => {
    const info = await fetchTunnelInfo();
    setUrl(info.url);
    setToken(info.token);
  }, []);

  useEffect(() => {
    refresh();
    const id = setInterval(refresh, POLL_INTERVAL);
    return () => clearInterval(id);
  }, [refresh]);

  return {
    url,
    token,
    visible,
    show: () => setVisible(true),
    hide: () => { setVisible(false); },
  };
}
