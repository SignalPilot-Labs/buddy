"use client";

import type { ReactElement } from "react";

// Status indicator icons — 9x9 or 10x10 viewBox, stroke-only styling.
// All icons accept an optional `color` prop and fall back to `currentColor`.
// Do NOT add icons to ToolIcons.tsx (already at 379 lines).

export function CheckmarkIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="9"
      height="9"
      viewBox="0 0 9 9"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <polyline points="1.5 4.5 3.5 6.5 7.5 2.5" />
    </svg>
  );
}

export function CrossIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="9"
      height="9"
      viewBox="0 0 9 9"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
    >
      <line x1="2" y1="2" x2="7" y2="7" />
      <line x1="7" y1="2" x2="2" y2="7" />
    </svg>
  );
}

export function WarningTriangleIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 12 12"
      fill="none"
      className="shrink-0"
    >
      <path
        d="M6 1L11 10H1L6 1Z"
        stroke={color || "currentColor"}
        strokeWidth="1"
        fill="none"
      />
      <line
        x1="6"
        y1="4.5"
        x2="6"
        y2="7"
        stroke={color || "currentColor"}
        strokeWidth="1"
        strokeLinecap="round"
      />
      <circle cx="6" cy="8.5" r="0.5" fill={color || "currentColor"} />
    </svg>
  );
}

export function SpinnerIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="10"
      height="10"
      viewBox="0 0 10 10"
      fill="none"
      className="animate-spin"
    >
      <circle
        cx="5"
        cy="5"
        r="4"
        stroke={color || "currentColor"}
        strokeWidth="1"
        strokeDasharray="12 8"
      />
    </svg>
  );
}

export function PauseIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="9"
      height="9"
      viewBox="0 0 9 9"
      fill="none"
    >
      <rect x="2" y="1.5" width="1.5" height="6" rx="0.5" fill={color || "currentColor"} />
      <rect x="5.5" y="1.5" width="1.5" height="6" rx="0.5" fill={color || "currentColor"} />
    </svg>
  );
}
