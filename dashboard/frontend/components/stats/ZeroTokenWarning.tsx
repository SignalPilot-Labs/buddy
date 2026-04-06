"use client";

import { ZERO_TOKEN_WARNING_MSG } from "@/lib/constants";

export interface ZeroTokenWarningProps {
  visible: boolean;
}

export function ZeroTokenWarning({ visible }: ZeroTokenWarningProps): React.ReactElement | null {
  if (!visible) return null;

  return (
    <div className="flex items-center gap-2 px-3 py-1.5 border-t border-[#ffaa00]/15 bg-[#ffaa00]/[0.04]">
      <svg
        width="12"
        height="12"
        viewBox="0 0 12 12"
        fill="none"
        stroke="#ffaa00"
        strokeWidth="1.5"
        strokeLinecap="round"
        className="shrink-0"
      >
        <path d="M6 1.5L10.5 9.5H1.5L6 1.5z" />
        <line x1="6" y1="5" x2="6" y2="7" />
        <circle cx="6" cy="8.5" r="0.4" fill="#ffaa00" stroke="none" />
      </svg>
      <span className="text-[9px] text-[#ffaa00]">{ZERO_TOKEN_WARNING_MSG}</span>
    </div>
  );
}
