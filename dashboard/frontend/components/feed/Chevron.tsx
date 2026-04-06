"use client";

import type { ReactElement } from "react";
import { clsx } from "clsx";

export function Chevron({ open, size }: { open: boolean; size: number }): ReactElement {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 10 10"
      fill="none"
      stroke="#888"
      strokeWidth="1.5"
      strokeLinecap="round"
      className={clsx("shrink-0 transition-transform duration-150", open && "rotate-90")}
    >
      <polyline points="3 2 7 5 3 8" />
    </svg>
  );
}
