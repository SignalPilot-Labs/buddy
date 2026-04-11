"use client";

import type { ReactElement } from "react";
import {
  MagnifyingGlassIcon,
  ClipboardDocumentListIcon,
  WrenchScrewdriverIcon,
  EyeIcon,
} from "@heroicons/react/24/outline";
import type { SubagentPhase } from "@/lib/phaseColors";
import { AgentIcon } from "@/components/ui/ToolIcons";

// Phase icons use Heroicons (outline 24) wrapped in a span that carries the
// dynamic phase color via `color` so the icons inherit it through
// currentColor. Semantically:
//   explore → magnifying glass (searching the codebase)
//   plan    → clipboard with list (drafting steps)
//   build   → wrench & screwdriver (making changes)
//   review  → eye (inspecting) — deliberately NOT a checkmark, which reads
//             as "done/success" and collides with card status semantics.

const ICON_CLASS = "h-[14px] w-[14px]";

function PhaseIconWrapper({
  Icon,
  color,
}: {
  Icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  color?: string;
}): ReactElement {
  return (
    <span
      className="inline-flex items-center justify-center"
      style={color ? { color } : undefined}
    >
      <Icon className={ICON_CLASS} strokeWidth={1.75} />
    </span>
  );
}

export function ExploreIcon({ color }: { color?: string }): ReactElement {
  return <PhaseIconWrapper Icon={MagnifyingGlassIcon} color={color} />;
}

export function PlanIcon({ color }: { color?: string }): ReactElement {
  return <PhaseIconWrapper Icon={ClipboardDocumentListIcon} color={color} />;
}

export function BuildIcon({ color }: { color?: string }): ReactElement {
  return <PhaseIconWrapper Icon={WrenchScrewdriverIcon} color={color} />;
}

export function ReviewIcon({ color }: { color?: string }): ReactElement {
  return <PhaseIconWrapper Icon={EyeIcon} color={color} />;
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
