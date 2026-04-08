/**Capacity-related derived state helpers for agent health.*/

import type { AgentHealth } from "./api";

export function isAtCapacity(agentHealth: AgentHealth | null): boolean {
  return (
    agentHealth !== null &&
    agentHealth.active_runs >= agentHealth.max_concurrent &&
    agentHealth.max_concurrent > 0
  );
}
