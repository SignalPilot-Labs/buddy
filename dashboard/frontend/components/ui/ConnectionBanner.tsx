"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RunStatus, ConnectionState } from "@/lib/types";
import { ACTIVE_STATUSES } from "@/lib/constants";
import type { ToastVariant } from "@/components/ui/Toast";

const BANNER_INITIAL = { opacity: 0, y: -8 };
const BANNER_ANIMATE = { opacity: 1, y: 0 };
const BANNER_EXIT = { opacity: 0, y: -8 };
const BANNER_TRANSITION = { duration: 0.2, ease: "easeOut" as const };

interface ConnectionBannerProps {
  connectionState: ConnectionState;
  runStatus: RunStatus | null;
  showToast: (message: string, variant: ToastVariant) => void;
}

export function ConnectionBanner({ connectionState, runStatus, showToast }: ConnectionBannerProps) {
  const isActiveRun = runStatus !== null && (ACTIVE_STATUSES as readonly string[]).includes(runStatus);
  const showBanner = connectionState !== "connected" && isActiveRun;

  const prevStateRef = useRef<ConnectionState>(connectionState);

  useEffect(() => {
    const prev = prevStateRef.current;
    prevStateRef.current = connectionState;

    if (connectionState === "connected" && prev !== "connected" && isActiveRun) {
      showToast("Reconnected", "success");
    }
  }, [connectionState, isActiveRun, showToast]);

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={BANNER_INITIAL}
          animate={BANNER_ANIMATE}
          exit={BANNER_EXIT}
          transition={BANNER_TRANSITION}
          role="alert"
          aria-live="assertive"
        >
          {connectionState === "reconnecting" ? (
            <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-center gap-2 px-4 py-1.5 bg-[var(--color-warning)]/10 border-b border-[var(--color-warning)]/20 frosted-glass">
              <span className="h-1.5 w-1.5 rounded-full border border-[var(--color-warning)] border-t-transparent animate-spin shrink-0" />
              <span className="text-meta text-[var(--color-warning)] font-medium">
                Reconnecting...
              </span>
            </div>
          ) : (
            <div className="absolute top-0 left-0 right-0 z-20 flex items-center justify-center gap-2 px-4 py-1.5 bg-[#ff4444]/10 border-b border-[#ff4444]/20 frosted-glass">
              <span className="h-1.5 w-1.5 rounded-full bg-[#ff4444] shrink-0" />
              <span className="text-meta text-[#ff4444] font-medium">
                Disconnected — events may be delayed
              </span>
            </div>
          )}
        </motion.div>
      )}
    </AnimatePresence>
  );
}
