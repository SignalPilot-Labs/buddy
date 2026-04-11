export type SubagentPhase = "explore" | "plan" | "build" | "review";

export interface PhaseMeta {
  label: string;
  color: string;
  textClass: string;
  borderClass: string;
}

export const SUBAGENT_PHASE_MAP: Record<string, SubagentPhase> = {
  "code-explorer": "explore",
  "debugger": "explore",
  "architect": "plan",
  "backend-dev": "build",
  "frontend-dev": "build",
  "code-reviewer": "review",
  "ui-reviewer": "review",
  "security-reviewer": "review",
};

export const PHASE_META: Record<SubagentPhase, PhaseMeta> = {
  explore: {
    label: "Explore",
    color: "#44ddff",
    textClass: "text-[#44ddff]",
    borderClass: "border-[#44ddff]",
  },
  plan: {
    label: "Plan",
    color: "#cc88ff",
    textClass: "text-[#cc88ff]",
    borderClass: "border-[#cc88ff]",
  },
  build: {
    label: "Build",
    color: "#00ff88",
    textClass: "text-[#00ff88]",
    borderClass: "border-[#00ff88]",
  },
  review: {
    label: "Review",
    color: "#ffaa00",
    textClass: "text-[#ffaa00]",
    borderClass: "border-[#ffaa00]",
  },
};

export const DEFAULT_PHASE_META: PhaseMeta = {
  label: "Agent",
  color: "#ff8844",
  textClass: "text-[#ff8844]",
  borderClass: "border-[#ff8844]",
};

export function resolvePhase(agentType: string): {
  phase: SubagentPhase | null;
  meta: PhaseMeta;
} {
  const phase = SUBAGENT_PHASE_MAP[agentType] ?? null;
  if (phase === null) {
    return { phase: null, meta: DEFAULT_PHASE_META };
  }
  return { phase, meta: PHASE_META[phase] };
}

export function hexToRgba(hex: string, alpha: number): string {
  const clean = hex.replace("#", "");
  const r = parseInt(clean.slice(0, 2), 16);
  const g = parseInt(clean.slice(2, 4), 16);
  const b = parseInt(clean.slice(4, 6), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
