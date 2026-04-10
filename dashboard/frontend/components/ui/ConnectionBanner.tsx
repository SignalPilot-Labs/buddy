"use client";

import { useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import type { RunStatus } from "@/lib/types";
import { ACTIVE_STATUSES } from "@/lib/constants";
import type { ToastVariant } from "@/components/ui/Toast";

const BANNER_INITIAL = { opacity: 0, y: -8 };
const BANNER_ANIMATE = { opacity: 1, y: 0 };
const BANNER_EXIT = { opacity: 0, y: -8 };
const BANNER_TRANSITION = { duration: 0.2, ease: "easeOut" as const };

interface ConnectionBannerProps {
  connected: boolean;
  runStatus: RunStatus | null;
  showToast: (message: string, variant: ToastVariant) => void;
}

export function ConnectionBanner({ connected, runStatus, showToast }: ConnectionBannerProps) {
  const isActiveRun = runStatus !== null && (ACTIVE_STATUSES as readonly string[]).includes(runStatus);
  const showBanner = !connected && isActiveRun;

  const prevConnectedRef = useRef(connected);

  useEffect(() => {
    const wasDisconnected = !prevConnectedRef.current;
    prevConnectedRef.current = connected;

    if (connected && wasDisconnected && isActiveRun) {
      showToast("Reconnected", "success");
    }
  }, [connected, isActiveRun, showToast]);

  return (
    <AnimatePresence>
      {showBanner && (
        <motion.div
          initial={BANNER_INITIAL}
          animate={BANNER_ANIMATE}
          exit={BANNER_EXIT}
          transition={BANNER_TRANSITION}
          className="absolute top-0 left-0 right-0 z-20 flex items-center justify-center gap-2 px-4 py-1.5 bg-[var(--color-warning)]/10 border-b border-[var(--color-warning)]/20 frosted-glass"
          role="alert"
          aria-live="assertive"
        >
          <span className="h-1.5 w-1.5 rounded-full bg-[var(--color-warning)] animate-pulse shrink-0" />
          <span className="text-[10px] text-[var(--color-warning)] font-medium">
            Connection lost — events may be delayed
          </span>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
