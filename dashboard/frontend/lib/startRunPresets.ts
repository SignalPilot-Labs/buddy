/** Presets, utilities, and static data for the StartRunModal. */

export interface DurationPreset {
  label: string;
  minutes: number;
  desc: string;
}

export interface QuickPrompt {
  label: string;
  prompt: string | undefined;
  desc: string;
}

export const DURATION_PRESETS: ReadonlyArray<DurationPreset> = [
  { label: "No lock", minutes: 0, desc: "Agent can end anytime" },
  { label: "30 min", minutes: 30, desc: "Quick pass" },
  { label: "1 hour", minutes: 60, desc: "Focused session" },
  { label: "2 hours", minutes: 120, desc: "Deep dive" },
  { label: "4 hours", minutes: 240, desc: "Extended run" },
  { label: "8 hours", minutes: 480, desc: "Overnight" },
];

export const QUICK_PROMPTS: ReadonlyArray<QuickPrompt> = [
  {
    label: "General improvement",
    prompt: undefined,
    desc: "Default: security, bugs, tests, quality",
  },
  {
    label: "Security hardening",
    prompt:
      "Focus on security: find and fix vulnerabilities, add input validation, review auth flows, check for injection risks.",
    desc: "Fix security issues",
  },
  {
    label: "Test coverage",
    prompt:
      "Focus exclusively on adding test coverage. Find untested critical paths and write thorough tests for them.",
    desc: "Add missing tests",
  },
  {
    label: "Bug fixes",
    prompt:
      "Focus on finding and fixing bugs: error handling gaps, edge cases, race conditions, incorrect logic. Run tests after each fix.",
    desc: "Find and fix bugs",
  },
];

export function parseEnvText(text: string): Record<string, string> {
  const result: Record<string, string> = {};
  for (const line of text.split("\n")) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#") || !trimmed.includes("=")) continue;
    const eqIdx = trimmed.indexOf("=");
    const key = trimmed.slice(0, eqIdx).trim();
    if (key) result[key] = trimmed.slice(eqIdx + 1);
  }
  return result;
}

export function envToText(env: Record<string, string>): string {
  return Object.entries(env)
    .map(([k, v]) => `${k}=${v}`)
    .join("\n");
}
