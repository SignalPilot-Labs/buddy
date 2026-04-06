"use client";

import { motion } from "framer-motion";
import { ERROR_STATUS_FALLBACK_MESSAGES } from "@/lib/constants";

export interface ErrorBannerProps {
  status: "error" | "crashed" | "killed";
  errorMessage: string | null;
}

export function ErrorBanner({ status, errorMessage }: ErrorBannerProps): React.ReactElement {
  const message = errorMessage ?? ERROR_STATUS_FALLBACK_MESSAGES[status];

  return (
    <motion.div
      initial={{ height: 0, opacity: 0 }}
      animate={{ height: "auto", opacity: 1 }}
      exit={{ height: 0, opacity: 0 }}
      className="px-4 py-2.5 border-b bg-[#ff4444]/[0.04] border-[#ff4444]/15"
    >
      <div className="flex items-center gap-3">
        <svg
          width="14"
          height="14"
          viewBox="0 0 14 14"
          fill="none"
          stroke="#ff4444"
          strokeWidth="1.5"
          strokeLinecap="round"
          className="shrink-0"
        >
          <path d="M7 1.5L12.5 11.5H1.5L7 1.5z" />
          <line x1="7" y1="5.5" x2="7" y2="8" />
          <circle cx="7" cy="9.5" r="0.5" fill="#ff4444" stroke="none" />
        </svg>

        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-semibold text-[#ff4444] capitalize">
              {status === "error" ? "Error" : status === "crashed" ? "Crashed" : "Killed"}
            </span>
          </div>
          <div className="text-[10px] text-[#ff4444]/80 mt-0.5">
            {message}
          </div>
        </div>
      </div>
    </motion.div>
  );
}
