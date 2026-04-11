// Phase color system for subagent cards.
//
// Each subagent type resolves to one of four phases (explore, plan, build,
// review). The phase determines the card's border, background, icon, and
// label color. Unknown agent types fall back to the default orange.
//
// IMPORTANT: Review's color (#ff66aa / pink) is deliberately distinct from
// the running-state amber (#ffaa00). Using the same hex for both would make
// a running `code-reviewer` card fully amber with no visual separation
// between phase and state — defeating the point of phase colors.

export type SubagentPhase = "explore" | "plan" | "build" | "review";

export interface PhaseMeta {
  label: string;
  color: string;
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
  explore: { label: "Explore", color: "#44ddff" }, // cyan
  plan:    { label: "Plan",    color: "#cc88ff" }, // purple
  build:   { label: "Build",   color: "#00ff88" }, // green
  review:  { label: "Review",  color: "#ff66aa" }, // pink — distinct from running-state amber
};

export const DEFAULT_PHASE_META: PhaseMeta = {
  label: "Agent",
  color: "#ff8844",
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

const HEX_COLOR_RE = /^#[0-9a-fA-F]{6}$/;

export function hexToRgba(hex: string, alpha: number): string {
  if (!HEX_COLOR_RE.test(hex)) {
    throw new Error(`hexToRgba: invalid hex color "${hex}" — expected #RRGGBB`);
  }
  if (alpha < 0 || alpha > 1) {
    throw new Error(`hexToRgba: alpha ${alpha} out of range [0, 1]`);
  }
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}
