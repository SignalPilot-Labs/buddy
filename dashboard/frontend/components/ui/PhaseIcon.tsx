"use client";

import type { ReactElement } from "react";
import type { SubagentPhase } from "@/lib/phaseColors";
import { AgentIcon } from "@/components/ui/ToolIcons";

export function ExploreIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="7" cy="7" r="5.5" />
      <polygon points="5,3.5 10.5,5 9,10.5 3.5,9" strokeWidth="1.2" />
    </svg>
  );
}

export function PlanIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <rect x="2.5" y="1.5" width="9" height="11" rx="1" />
      <line x1="5" y1="4.5" x2="9.5" y2="4.5" />
      <line x1="5" y1="7" x2="9.5" y2="7" />
      <line x1="5" y1="9.5" x2="8" y2="9.5" />
    </svg>
  );
}

export function BuildIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M8.5 2.5L5 6l2 2 3.5-3.5" />
      <path d="M5 6L2 12l6-3-2-2" />
    </svg>
  );
}

export function ReviewIcon({ color }: { color?: string }): ReactElement {
  return (
    <svg
      width="14"
      height="14"
      viewBox="0 0 14 14"
      fill="none"
      stroke={color || "currentColor"}
      strokeWidth="1.5"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="7" cy="7" r="5.5" />
      <polyline points="4.5 7 6.5 9 9.5 5" />
    </svg>
  );
}

export function getPhaseIcon(
  phase: SubagentPhase | null,
  color?: string
): ReactElement {
  switch (phase) {
    case "explore":
      return <ExploreIcon color={color} />;
    case "plan":
      return <PlanIcon color={color} />;
    case "build":
      return <BuildIcon color={color} />;
    case "review":
      return <ReviewIcon color={color} />;
    default:
      return <AgentIcon color={color} />;
  }
}
