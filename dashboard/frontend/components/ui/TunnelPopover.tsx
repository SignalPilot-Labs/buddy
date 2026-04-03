"use client";

import { useState, useRef, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTunnel } from "@/hooks/useTunnel";
import { Button } from "./Button";

export function TunnelPopover() {
  const [open, setOpen] = useState(false);
  const [copiedUrl, setCopiedUrl] = useState(false);
  const [copiedCode, setCopiedCode] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const { url, token, visible, show, hide } = useTunnel();

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const copyText = async (text: string, setter: (v: boolean) => void) => {
    await navigator.clipboard.writeText(text);
    setter(true);
    setTimeout(() => setter(false), 2000);
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
        {visible && url && (
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
            className="absolute top-full right-0 mt-1 z-50 w-[300px] bg-[#0a0a0a] border border-[#1a1a1a] rounded-lg shadow-xl shadow-black/50 overflow-hidden"
          >
            <div className="px-3 py-2 border-b border-[#1a1a1a]">
              <span className="text-[9px] uppercase tracking-[0.1em] text-[#666] font-semibold">
                Mobile Access
              </span>
            </div>

            <div className="p-3 space-y-3">
              {visible && url && token && (
                <>
                  {/* URL */}
                  <div>
                    <label className="text-[9px] uppercase tracking-[0.1em] text-[#555] font-semibold mb-1 block">URL</label>
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 min-w-0 px-2 py-1.5 bg-white/[0.03] border border-[#1a1a1a] rounded text-[10px] text-[#88ccff] font-mono truncate">
                        {url}
                      </div>
                      <button
                        onClick={() => copyText(url, setCopiedUrl)}
                        className="shrink-0 p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
                        title="Copy URL"
                      >
                        {copiedUrl ? (
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
                  </div>

                  {/* Pairing Code */}
                  <div>
                    <label className="text-[9px] uppercase tracking-[0.1em] text-[#555] font-semibold mb-1 block">Access Code</label>
                    <div className="flex items-center gap-1.5">
                      <div className="flex-1 min-w-0 px-2 py-1.5 bg-white/[0.03] border border-[#1a1a1a] rounded text-[13px] text-[#00ff88] font-mono font-bold tracking-widest text-center">
                        {token}
                      </div>
                      <button
                        onClick={() => copyText(token, setCopiedCode)}
                        className="shrink-0 p-1.5 rounded hover:bg-white/[0.04] text-[#888] hover:text-[#ccc] transition-colors"
                        title="Copy access code"
                      >
                        {copiedCode ? (
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
                  </div>

                  <p className="text-[10px] text-[#666] leading-relaxed">
                    Open the URL on your phone, then enter the access code when prompted. Code rotates on restart.
                  </p>
                </>
              )}

              {visible && !url && (
                <p className="text-[10px] text-[#666]">
                  Waiting for tunnel URL...
                </p>
              )}

              {!visible && (
                <p className="text-[10px] text-[#666]">
                  {url ? "Tunnel is ready. Click below to reveal connection details." : "Tunnel is starting..."}
                </p>
              )}

              <Button
                variant={visible ? "danger" : "success"}
                size="sm"
                onClick={visible ? hide : show}
                icon={
                  visible ? (
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="currentColor">
                      <rect x="2" y="2" width="6" height="6" rx="1" />
                    </svg>
                  ) : (
                    <svg width="10" height="10" viewBox="0 0 10 10" fill="none" stroke="currentColor" strokeWidth="1.5">
                      <polygon points="3 2 8 5 3 8" />
                    </svg>
                  )
                }
              >
                {visible ? "Hide" : "Show Access"}
              </Button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
