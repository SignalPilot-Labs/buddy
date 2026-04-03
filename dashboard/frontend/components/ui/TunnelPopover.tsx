"use client";

import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTunnel } from "@/hooks/useTunnel";
import { Button } from "@/components/ui/Button";

export function TunnelPopover() {
  const { status, url, loading, start, stop } = useTunnel();
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  const isRunning = status === "running";

  // Close on click outside
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleCopy = async () => {
    if (!url) return;
    await navigator.clipboard.writeText(url);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const statusColor =
    status === "running"
      ? "bg-[#00ff88]"
      : status === "exited" || status === "not_found"
        ? "bg-[#ff4444]/60"
        : "bg-[#ffaa00]";

  const statusLabel =
    status === "running"
      ? "Running"
      : status === "exited"
        ? "Stopped"
        : status === "not_found"
          ? "Not Found"
          : status === "restarting"
            ? "Restarting"
            : "Error";

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="relative p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
        title="Tunnel"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
          <line x1="12" y1="18" x2="12.01" y2="18" />
        </svg>
        {isRunning && (
          <span className="absolute top-0.5 right-0.5 h-1.5 w-1.5 rounded-full bg-[#00ff88]" />
        )}
      </button>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -4 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -4 }}
            transition={{ duration: 0.15 }}
            className="absolute top-full right-0 mt-1 z-50 w-[280px] bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg p-3 space-y-3"
          >
            {/* Status */}
            <div className="flex items-center gap-2">
              <span className={`h-2 w-2 rounded-full ${statusColor}`} />
              <span className="text-[11px] text-[#e8e8e8] font-medium">Tunnel</span>
              <span className="text-[10px] text-[#888]">{statusLabel}</span>
            </div>

            {/* URL */}
            {isRunning && url && (
              <div className="flex items-center gap-1.5">
                <div className="flex-1 min-w-0 bg-[#080808] border border-[#1a1a1a] rounded px-2 py-1">
                  <span className="text-[10px] text-[#999] font-mono block truncate">{url}</span>
                </div>
                <button
                  onClick={handleCopy}
                  className="p-1 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors shrink-0"
                  title="Copy URL"
                >
                  {copied ? (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00ff88" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="20 6 9 17 4 12" />
                    </svg>
                  ) : (
                    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="9" y="9" width="13" height="13" rx="2" ry="2" />
                      <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                    </svg>
                  )}
                </button>
              </div>
            )}
            {isRunning && !url && (
              <p className="text-[10px] text-[#666]">Waiting for tunnel URL...</p>
            )}

            {/* Actions */}
            {isRunning ? (
              <Button
                variant="danger"
                size="sm"
                onClick={stop}
                disabled={loading}
                className="w-full justify-center"
              >
                {loading ? "..." : "Stop Tunnel"}
              </Button>
            ) : (
              <Button
                variant="success"
                size="sm"
                onClick={start}
                disabled={loading}
                className="w-full justify-center"
              >
                {loading ? "..." : "Start Tunnel"}
              </Button>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
