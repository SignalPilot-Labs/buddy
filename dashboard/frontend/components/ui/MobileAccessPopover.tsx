"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { QRCodeSVG } from "qrcode.react";
import { useNetworkInfo } from "@/hooks/useNetworkInfo";

export function MobileAccessPopover() {
  const [open, setOpen] = useState(false);
  const [copied, setCopied] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { url } = useNetworkInfo();

  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", handleClick);
    document.addEventListener("keydown", handleKey);
    return () => {
      document.removeEventListener("mousedown", handleClick);
      document.removeEventListener("keydown", handleKey);
    };
  }, [open]);

  const copyUrl = async () => {
    if (!url) return;
    try {
      await navigator.clipboard.writeText(url);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Clipboard API not available (e.g., non-HTTPS context)
    }
  };

  return (
    <div ref={ref} className="relative">
      <button
        onClick={() => setOpen(!open)}
        className="relative p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
        title="Mobile Access"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="5" y="2" width="14" height="20" rx="2" ry="2" />
          <line x1="12" y1="18" x2="12.01" y2="18" />
        </svg>
        {url && (
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
            className="absolute top-full right-0 mt-1 z-50 w-[260px] bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg shadow-xl shadow-black/50 overflow-hidden"
          >
            <div className="px-3 py-2 border-b border-[#1a1a1a]">
              <span className="text-[10px] uppercase tracking-[0.1em] text-[#666] font-semibold">
                Mobile Access
              </span>
            </div>

            <div className="p-3 space-y-3">
              {url ? (
                <>
                  <div className="flex justify-center bg-white rounded-lg p-3">
                    <QRCodeSVG value={url} size={160} level="M" />
                  </div>

                  <div className="flex items-center gap-1.5">
                    <div className="flex-1 min-w-0 px-2 py-1.5 bg-white/[0.03] border border-[#1a1a1a] rounded text-[10px] text-[#88ccff] font-mono truncate">
                      {url}
                    </div>
                    <button
                      onClick={copyUrl}
                      className="shrink-0 p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
                      title="Copy URL"
                    >
                      {copied ? (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#00ff88" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                          <polyline points="20 6 9 17 4 12" />
                        </svg>
                      ) : (
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                          <rect x="9" y="9" width="13" height="13" rx="2" />
                          <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1" />
                        </svg>
                      )}
                    </button>
                  </div>

                  <p className="text-[10px] text-[#666] leading-relaxed">
                    Scan from your phone on the same WiFi network.
                  </p>
                </>
              ) : (
                <p className="text-[10px] text-[#666] leading-relaxed">
                  Could not detect local network IP. Start with{" "}
                  <span className="font-mono text-[#888]">./start.sh</span> or set{" "}
                  <span className="font-mono text-[#888]">HOST_IP</span> env var.
                </p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
