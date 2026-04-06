import type { ToolCall, AuditEvent, FeedEvent } from "@/lib/types";

const EXCLUDED_AUDIT_TYPES = ["llm_text", "llm_thinking"];

function mergePrePost(tools: ToolCall[]): ToolCall[] {
  const merged: ToolCall[] = [];

  for (const tc of tools) {
    if (tc.phase === "pre") {
      merged.push({ ...tc });
      continue;
    }

    let matched = false;

    if (tc.tool_use_id) {
      for (let j = merged.length - 1; j >= 0; j--) {
        const pre = merged[j];
        if (pre.tool_use_id === tc.tool_use_id && pre.phase === "pre") {
          pre.output_data = tc.output_data;
          pre.duration_ms = tc.duration_ms;
          pre.phase = "post";
          matched = true;
          break;
        }
      }
    }

    if (!matched) {
      for (let j = merged.length - 1; j >= 0; j--) {
        const pre = merged[j];
        if (
          pre.tool_name === tc.tool_name &&
          pre.phase === "pre" &&
          !pre.output_data
        ) {
          pre.output_data = tc.output_data;
          pre.duration_ms = tc.duration_ms;
          pre.phase = "post";
          matched = true;
          break;
        }
      }
    }

    if (!matched) {
      merged.push({ ...tc });
    }
  }

  return merged;
}

function getFeedEventTs(e: FeedEvent): string {
  if (e._kind === "tool") return e.data.ts;
  if (e._kind === "audit") return e.data.ts;
  if (e._kind === "usage") return e.data.ts;
  return e.ts;
}

export function buildHistoryEvents(
  tools: ToolCall[],
  audits: AuditEvent[],
): FeedEvent[] {
  tools.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());
  audits.sort((a, b) => new Date(a.ts).getTime() - new Date(b.ts).getTime());

  const mergedTools = mergePrePost(tools);

  const toolEvents: FeedEvent[] = mergedTools.map((tc) => ({
    _kind: "tool" as const,
    data: tc,
  }));

  const auditEvents: FeedEvent[] = audits
    .filter((a) => !EXCLUDED_AUDIT_TYPES.includes(a.event_type))
    .map((a) => ({
      _kind: "audit" as const,
      data: a,
    }));

  return [...toolEvents, ...auditEvents].sort(
    (a, b) =>
      new Date(getFeedEventTs(a)).getTime() -
      new Date(getFeedEventTs(b)).getTime(),
  );
}
